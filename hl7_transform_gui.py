# -*- coding: utf-8 -*-
# HL7 Process GUI (Jython + LightHL7)
# - Left: Before (HL7 input)
# - Middle: After (output from process(inString))
# - Right: Python syntax-highlighted editor (RSyntaxTextArea)
# - Diff: highlight only differing HL7 sections per line (| ^ &) and IGNORE line-ending differences (\r, \n, \r\n)

from javax.swing import (
    JFrame, JPanel, JButton, JCheckBox, JLabel, JTextArea, JScrollPane, JSplitPane,
    JFileChooser, JOptionPane, SwingUtilities, BorderFactory, UIManager,
    JTextField, JComponent, KeyStroke, AbstractAction, JDialog, ToolTipManager
)
from javax.swing.text import DefaultHighlighter, JTextComponent
from javax.swing.undo import UndoManager
from javax.swing.event import DocumentListener
from javax.swing.plaf.basic import BasicButtonUI, BasicScrollBarUI, BasicSplitPaneUI
from java.awt import BorderLayout, Dimension, Color, Font, GridLayout, Insets, KeyboardFocusManager
from java.awt.event import KeyEvent, InputEvent, FocusAdapter, MouseMotionAdapter
from java.util.prefs import Preferences
from StringIO import StringIO
import traceback
import os
import re
import sys

# If needed, add RSyntaxTextArea jar to sys.path at runtime (uncomment below)
# import sys
# jar_path = os.path.join(os.path.dirname(__file__), 'lib', 'rsyntaxtextarea-3.3.4.jar')
# if os.path.exists(jar_path):
#     sys.path.append(jar_path)

from org.fife.ui.rsyntaxtextarea import RSyntaxTextArea, SyntaxConstants
from org.fife.ui.rtextarea import RTextScrollPane


def read_file(path):
    with open(path, 'r') as f:
        return f.read()


def write_file(path, content):
    with open(path, 'w') as f:
        f.write(content)


class FlatScrollBarUI(BasicScrollBarUI):
    def __init__(self, thumbColor, trackColor):
        BasicScrollBarUI.__init__(self)
        self.flatThumbColor = thumbColor
        self.flatTrackColor = trackColor

    def configureScrollBarColors(self):
        self.thumbColor = self.flatThumbColor
        self.trackColor = self.flatTrackColor

    def paintTrack(self, graphics, component, bounds):
        graphics.setColor(self.flatTrackColor)
        graphics.fillRect(bounds.x, bounds.y, bounds.width, bounds.height)

    def paintThumb(self, graphics, component, bounds):
        if bounds.isEmpty() or not component.isEnabled():
            return
        graphics.setColor(self.flatThumbColor)
        graphics.fillRoundRect(bounds.x + 2, bounds.y + 2, bounds.width - 4, bounds.height - 4, 8, 8)

    def createDecreaseButton(self, orientation):
        return self.emptyScrollButton()

    def createIncreaseButton(self, orientation):
        return self.emptyScrollButton()

    def emptyScrollButton(self):
        button = JButton()
        size = Dimension(1, 1)
        button.setPreferredSize(size)
        button.setMinimumSize(size)
        button.setMaximumSize(size)
        button.setBorder(BorderFactory.createEmptyBorder())
        button.setOpaque(True)
        button.setBackground(self.flatTrackColor)
        return button


class TextFocusTracker(FocusAdapter):
    def __init__(self, gui, area):
        FocusAdapter.__init__(self)
        self.gui = gui
        self.area = area

    def focusGained(self, event):
        self.gui.activeTextArea = self.area


class ShortcutAction(AbstractAction):
    def __init__(self, callback):
        AbstractAction.__init__(self)
        self.callback = callback

    def actionPerformed(self, event):
        self.callback()


class ScriptChangeListener(DocumentListener):
    def __init__(self, gui, area, button):
        DocumentListener.__init__(self)
        self.gui = gui
        self.area = area
        self.button = button

    def insertUpdate(self, event):
        self.gui.resetCompileButton(self.area, self.button)

    def removeUpdate(self, event):
        self.gui.resetCompileButton(self.area, self.button)

    def changedUpdate(self, event):
        self.gui.resetCompileButton(self.area, self.button)


class ScriptErrorToolTipListener(MouseMotionAdapter):
    def __init__(self, gui, area):
        MouseMotionAdapter.__init__(self)
        self.gui = gui
        self.area = area

    def mouseMoved(self, event):
        self.gui.updateScriptErrorToolTip(self.area, event)


class HL7TransformGUI(JFrame):
    def __init__(self):
        try:
            UIManager.setLookAndFeel(UIManager.getSystemLookAndFeelClassName())
        except Exception:
            pass

        JFrame.__init__(self, "HL7 Process (Jython + LightHL7)")
        self.setDefaultCloseOperation(JFrame.EXIT_ON_CLOSE)
        self.setPreferredSize(Dimension(1200, 750))

        self.bgColor = Color(242, 246, 248)
        self.panelColor = Color(255, 255, 255)
        self.borderColor = Color(205, 216, 222)
        self.labelColor = Color(38, 58, 67)
        self.accentColor = Color(42, 166, 151)
        self.runColor = Color(34, 139, 89)
        self.runBorderColor = Color(24, 105, 67)
        self.codeBgColor = Color(250, 252, 252)
        self.textColor = Color(29, 42, 48)
        self.textFont = Font("Consolas", Font.PLAIN, 14)
        self.labelFont = Font("Segoe UI", Font.BOLD, 13)
        self.panePanels = []
        self.paneLabels = []
        self.scrollPanes = []
        self.splitPanes = []
        self.outputAreas = []
        self.outputPanes = []
        self.outputHeaders = []
        self.scriptAreas = []
        self.scriptPanes = []
        self.scriptHeaders = []
        self.scriptHeaderControls = []
        self.scriptToggles = []
        self.scriptCompileButtons = []
        self.scriptTagsButtons = []
        self.scriptRejectButtons = []
        self.scriptScrollPanes = []
        self.scriptCompileErrorLines = {}
        self.scriptCompileErrorHighlights = {}
        self.maxScripts = 4
        self.activeTextArea = None
        self.undoManagers = {}
        self.searchLabels = []
        self.preferences = Preferences.userRoot().node("HL7TransformGUI")
        self.darkMode = self.preferences.getBoolean("darkMode", False)
        self.consoleDialog = None
        self.consolePanel = None
        self.consoleTopPanel = None
        self.consoleArea = None
        self.consoleScrollPane = None
        self.consoleClearBtn = None
        self.consoleBuffer = ""

        # Top controls
        self.topPanel = JPanel()
        self.topPanel.setBorder(BorderFactory.createEmptyBorder(10, 12, 8, 12))
        self.runBtn = JButton("Run process(inString)")
        self.runBtn.setFont(Font("Segoe UI", Font.BOLD, 13))
        self.runBtn.setForeground(Color(255, 255, 255))
        self.runBtn.setBackground(self.runColor)
        self.runBtn.setUI(BasicButtonUI())
        self.runBtn.setOpaque(True)
        self.runBtn.setContentAreaFilled(True)
        self.runBtn.setFocusPainted(False)
        self.runBtn.setBorderPainted(True)
        self.runBtn.setBorder(BorderFactory.createCompoundBorder(
            BorderFactory.createLineBorder(self.runBorderColor, 1),
            BorderFactory.createEmptyBorder(7, 14, 7, 14)
        ))
        self.addScriptBtn = self.scriptControlButton("+")
        self.removeScriptBtn = self.scriptControlButton("-")
        self.themeToggle = JCheckBox("Dark mode")
        self.themeToggle.setFont(Font("Segoe UI", Font.PLAIN, 12))
        self.themeToggle.setFocusPainted(False)
        self.themeToggle.setSelected(self.darkMode)
        self.findToggleBtn = self.toolbarButton("Find/Replace")
        self.consoleBtn = self.toolbarButton(">_ Console")
        self.consoleBtn.setToolTipText("Show script print output")
        self.findField = JTextField(14)
        self.replaceField = JTextField(14)
        self.findBtn = self.toolbarButton("Find")
        self.replaceBtn = self.toolbarButton("Replace")
        self.replaceAllBtn = self.toolbarButton("Replace All")
        self.scriptPath = ""

        self.topPanel.add(self.runBtn)
        findLabel = JLabel("Find")
        replaceLabel = JLabel("Replace")
        self.searchLabels.append(findLabel)
        self.searchLabels.append(replaceLabel)
        self.topPanel.add(self.findToggleBtn)
        self.topPanel.add(self.consoleBtn)
        self.findReplacePanel = JPanel()
        self.findReplacePanel.add(findLabel)
        self.findReplacePanel.add(self.findField)
        self.findReplacePanel.add(self.findBtn)
        self.findReplacePanel.add(replaceLabel)
        self.findReplacePanel.add(self.replaceField)
        self.findReplacePanel.add(self.replaceBtn)
        self.findReplacePanel.add(self.replaceAllBtn)
        self.findReplacePanel.setVisible(False)
        self.topPanel.add(self.findReplacePanel)
        self.topPanel.add(self.themeToggle)

        # Before/After text areas
        self.beforeArea = self.createHL7Area()

        inputPanel = JPanel(BorderLayout())
        inputPanel.add(self.paneLabel("Input HL7"), BorderLayout.NORTH)
        inputPanel.add(self.cleanScrollPane(self.beforeArea), BorderLayout.CENTER)
        self.panePanels.append(inputPanel)

        outputPanel = JPanel(BorderLayout())
        outputPanel.add(self.paneLabel("Output HL7"), BorderLayout.NORTH)
        self.outputStackPanel = JPanel()
        self.outputStackPanel.setLayout(GridLayout(0, 1, 0, 6))
        outputPanel.add(self.outputStackPanel, BorderLayout.CENTER)
        self.panePanels.append(outputPanel)

        leftSplit = JSplitPane(
            JSplitPane.HORIZONTAL_SPLIT,
            inputPanel,
            outputPanel
        )
        leftSplit.setResizeWeight(0.5)
        leftSplit.setDividerSize(8)
        leftSplit.setUI(BasicSplitPaneUI())
        self.splitPanes.append(leftSplit)

        rightPanel = JPanel(BorderLayout())
        self.scriptTitlePanel = JPanel(BorderLayout())
        self.scriptControlPanel = JPanel()
        self.scriptControlPanel.add(self.addScriptBtn)
        self.scriptControlPanel.add(self.removeScriptBtn)
        self.scriptTitlePanel.add(self.paneLabel("Jython Scripts"), BorderLayout.WEST)
        self.scriptTitlePanel.add(self.scriptControlPanel, BorderLayout.EAST)
        rightPanel.add(self.scriptTitlePanel, BorderLayout.NORTH)
        self.scriptStackPanel = JPanel()
        self.scriptStackPanel.setLayout(GridLayout(0, 1, 0, 6))
        rightPanel.add(self.scriptStackPanel, BorderLayout.CENTER)
        self.panePanels.append(rightPanel)
        self.addScriptPane()

        mainSplit = JSplitPane(
            JSplitPane.HORIZONTAL_SPLIT,
            leftSplit,
            rightPanel
        )
        mainSplit.setResizeWeight(0.6)
        mainSplit.setDividerSize(8)
        mainSplit.setUI(BasicSplitPaneUI())
        self.splitPanes.append(mainSplit)

        self.getContentPane().setLayout(BorderLayout())
        self.getContentPane().add(self.topPanel, BorderLayout.NORTH)
        self.getContentPane().add(mainSplit, BorderLayout.CENTER)

        # Actions
        self.runBtn.addActionListener(self.onRun)
        self.addScriptBtn.addActionListener(self.addScriptPane)
        self.removeScriptBtn.addActionListener(self.removeScriptPane)
        self.themeToggle.addActionListener(lambda e: self.onThemeToggle())
        self.findToggleBtn.addActionListener(lambda e: self.toggleFindReplace())
        self.consoleBtn.addActionListener(lambda e: self.showConsole())
        self.findBtn.addActionListener(lambda e: self.findNext(False))
        self.replaceBtn.addActionListener(lambda e: self.replaceCurrent())
        self.replaceAllBtn.addActionListener(lambda e: self.replaceAll())
        self.findField.addActionListener(lambda e: self.findNext(False))
        self.replaceField.addActionListener(lambda e: self.replaceCurrent())
        self.installSearchShortcuts()

        # Highlighters
        self.painterDelete = None
        self.painterInsert = None
        self.painterReplace = None

        # Regex to split while keeping delimiters as tokens
        # If you also want "~" treated as a delimiter, include it in the char class: r'([|\^&~])'
        self.hl7_split_regex = re.compile(r'([|\^&])')

        self.applyTheme(self.darkMode)
        self.pack()
        self.setLocationRelativeTo(None)

    def createHL7Area(self):
        area = JTextArea()
        area.setLineWrap(True)
        area.setWrapStyleWord(True)
        area.setFont(self.textFont)
        area.setCaretColor(self.accentColor)
        area.setMargin(Insets(10, 10, 10, 10))
        self.registerTextArea(area)
        return area

    def scriptControlButton(self, text):
        button = JButton(text)
        button.setFont(Font("Segoe UI", Font.BOLD, 15))
        button.setUI(BasicButtonUI())
        button.setOpaque(True)
        button.setContentAreaFilled(True)
        button.setFocusPainted(False)
        button.setBorderPainted(True)
        button.setPreferredSize(Dimension(34, 26))
        return button

    def toolbarButton(self, text):
        button = JButton(text)
        button.setFont(Font("Segoe UI", Font.BOLD, 12))
        button.setUI(BasicButtonUI())
        button.setOpaque(True)
        button.setContentAreaFilled(True)
        button.setFocusPainted(False)
        button.setBorderPainted(True)
        return button

    def registerTextArea(self, area):
        area.addFocusListener(TextFocusTracker(self, area))
        undoManager = UndoManager()
        area.getDocument().addUndoableEditListener(lambda event, manager=undoManager: manager.addEdit(event.getEdit()))
        self.undoManagers[area] = undoManager
        inputMap = area.getInputMap()
        actionMap = area.getActionMap()
        inputMap.put(KeyStroke.getKeyStroke(KeyEvent.VK_Z, InputEvent.CTRL_DOWN_MASK), "undoEdit")
        actionMap.put("undoEdit", ShortcutAction(self.undoCurrentTextArea))
        inputMap.put(KeyStroke.getKeyStroke(KeyEvent.VK_Y, InputEvent.CTRL_DOWN_MASK), "redoEdit")
        actionMap.put("redoEdit", ShortcutAction(self.redoCurrentTextArea))
        inputMap.put(KeyStroke.getKeyStroke(KeyEvent.VK_Z, InputEvent.CTRL_DOWN_MASK | InputEvent.SHIFT_DOWN_MASK), "redoEdit")
        if self.activeTextArea is None:
            self.activeTextArea = area

    def createScriptArea(self):
        area = RSyntaxTextArea()
        area.setSyntaxEditingStyle(SyntaxConstants.SYNTAX_STYLE_PYTHON)
        area.setCodeFoldingEnabled(True)
        area.setAntiAliasingEnabled(True)
        area.setTabsEmulated(True)
        area.setTabSize(4)
        area.setBracketMatchingEnabled(True)
        area.setFont(self.textFont)
        area.setCaretColor(self.accentColor)
        area.setMargin(Insets(10, 10, 10, 10))
        self.registerTextArea(area)
        area.setToolTipText(" ")
        ToolTipManager.sharedInstance().registerComponent(area)
        area.addMouseMotionListener(ScriptErrorToolTipListener(self, area))
        return area

    def addOutputPane(self, outputNumber):
        area = self.createHL7Area()
        area.setEditable(False)

        header = JPanel(BorderLayout())
        header.add(self.paneLabel("After Script %d" % outputNumber), BorderLayout.WEST)

        panel = JPanel(BorderLayout())
        panel.add(header, BorderLayout.NORTH)
        panel.add(self.cleanScrollPane(area), BorderLayout.CENTER)

        self.outputAreas.append(area)
        self.outputPanes.append(panel)
        self.outputHeaders.append(header)
        self.panePanels.append(panel)
        self.outputStackPanel.add(panel)
        self.afterArea = area

    def removeOutputPane(self):
        if len(self.outputAreas) <= 1:
            return

        panel = self.outputPanes.pop()
        self.outputAreas.pop()
        self.outputHeaders.pop()
        scrollPane = None
        for component in panel.getComponents():
            if isinstance(component, JScrollPane):
                scrollPane = component
                break

        if panel in self.panePanels:
            self.panePanels.remove(panel)
        if scrollPane is not None and scrollPane in self.scrollPanes:
            self.scrollPanes.remove(scrollPane)

        self.outputStackPanel.remove(panel)
        self.afterArea = self.outputAreas[-1]

    def addScriptPane(self, event=None):
        if len(self.scriptAreas) >= self.maxScripts:
            return

        scriptNumber = len(self.scriptAreas) + 1
        area = self.createScriptArea()
        area.setText(self.default_script_template(scriptNumber))

        toggle = JCheckBox("Enabled")
        toggle.setSelected(True)
        toggle.setFont(Font("Segoe UI", Font.PLAIN, 12))
        toggle.setFocusPainted(False)
        toggle.addActionListener(lambda e: self.onScriptToggle())
        compileBtn = self.toolbarButton("Compile")
        tagsBtn = self.toolbarButton("Test getTags")
        rejectBtn = self.toolbarButton("Test isRejected")

        header = JPanel(BorderLayout())
        header.add(self.paneLabel("Jython Script %d" % scriptNumber), BorderLayout.WEST)
        headerControls = JPanel()
        headerControls.add(compileBtn)
        headerControls.add(tagsBtn)
        headerControls.add(rejectBtn)
        headerControls.add(toggle)
        header.add(headerControls, BorderLayout.EAST)
        self.scriptHeaderControls.append(headerControls)
        compileBtn.addActionListener(lambda e, button=compileBtn: self.compileScriptForButton(button))
        tagsBtn.addActionListener(lambda e, button=tagsBtn: self.testGetTagsForButton(button))
        rejectBtn.addActionListener(lambda e, button=rejectBtn: self.testIsRejectedForButton(button))
        area.getDocument().addDocumentListener(ScriptChangeListener(self, area, compileBtn))

        scrollPane = RTextScrollPane(area)
        panel = JPanel(BorderLayout())
        panel.add(header, BorderLayout.NORTH)
        panel.add(self.cleanScrollPane(scrollPane), BorderLayout.CENTER)

        self.scriptAreas.append(area)
        self.scriptPanes.append(panel)
        self.scriptHeaders.append(header)
        self.scriptToggles.append(toggle)
        self.scriptCompileButtons.append(compileBtn)
        self.scriptTagsButtons.append(tagsBtn)
        self.scriptRejectButtons.append(rejectBtn)
        self.scriptScrollPanes.append(scrollPane)
        self.scriptCompileErrorLines[area] = {}
        self.scriptCompileErrorHighlights[area] = []
        self.panePanels.append(panel)
        self.scriptStackPanel.add(panel)
        self.addOutputPane(scriptNumber)

        self.updateScriptControls()
        self.applyTheme(self.themeToggle.isSelected())
        self.scriptStackPanel.revalidate()
        self.scriptStackPanel.repaint()
        self.outputStackPanel.revalidate()
        self.outputStackPanel.repaint()

    def removeScriptPane(self, event=None):
        if len(self.scriptAreas) <= 1:
            return

        panel = self.scriptPanes.pop()
        area = self.scriptAreas.pop()
        self.scriptHeaders.pop()
        self.scriptHeaderControls.pop()
        self.scriptToggles.pop()
        self.scriptCompileButtons.pop()
        self.scriptTagsButtons.pop()
        self.scriptRejectButtons.pop()
        scrollPane = self.scriptScrollPanes.pop()
        self.clearCompileErrorHighlight(area)
        if self.scriptCompileErrorLines.has_key(area):
            del self.scriptCompileErrorLines[area]
        if self.scriptCompileErrorHighlights.has_key(area):
            del self.scriptCompileErrorHighlights[area]

        if panel in self.panePanels:
            self.panePanels.remove(panel)
        if scrollPane in self.scrollPanes:
            self.scrollPanes.remove(scrollPane)

        self.scriptStackPanel.remove(panel)
        self.removeOutputPane()
        self.updateScriptControls()
        self.applyTheme(self.themeToggle.isSelected())
        self.scriptStackPanel.revalidate()
        self.scriptStackPanel.repaint()
        self.outputStackPanel.revalidate()
        self.outputStackPanel.repaint()

        if self.beforeArea.getText().strip():
            self.runPipeline(True)

    def updateScriptControls(self):
        self.addScriptBtn.setEnabled(len(self.scriptAreas) < self.maxScripts)
        self.removeScriptBtn.setEnabled(len(self.scriptAreas) > 1)

    def paneLabel(self, text):
        label = JLabel(text)
        label.setFont(self.labelFont)
        label.setOpaque(True)
        self.paneLabels.append(label)
        return label

    def paneBorder(self):
        return BorderFactory.createCompoundBorder(
            BorderFactory.createEmptyBorder(6, 6, 8, 6),
            BorderFactory.createLineBorder(self.borderColor, 1)
        )

    def cleanScrollPane(self, content):
        if isinstance(content, JScrollPane):
            scrollPane = content
        else:
            scrollPane = JScrollPane(content)
        scrollPane.setBorder(BorderFactory.createMatteBorder(1, 0, 0, 0, self.borderColor))
        scrollPane.getViewport().setBackground(self.codeBgColor)
        self.scrollPanes.append(scrollPane)
        return scrollPane

    def applyTheme(self, darkMode):
        if darkMode:
            self.bgColor = Color(31, 39, 43)
            self.panelColor = Color(39, 49, 54)
            self.borderColor = Color(77, 91, 97)
            self.labelColor = Color(227, 235, 237)
            self.codeBgColor = Color(24, 31, 34)
            self.textColor = Color(230, 235, 236)
            self.accentColor = Color(61, 184, 160)
            self.runColor = Color(42, 157, 102)
            self.runBorderColor = Color(85, 205, 142)
            scrollThumbColor = Color(92, 111, 118)
            scrollTrackColor = Color(30, 38, 42)
            dividerColor = Color(61, 74, 80)
            gutterBgColor = Color(30, 38, 42)
            gutterTextColor = Color(150, 169, 176)
            self.painterDelete = DefaultHighlighter.DefaultHighlightPainter(Color(96, 49, 54))
            self.painterInsert = DefaultHighlighter.DefaultHighlightPainter(Color(48, 87, 62))
            self.painterReplace = DefaultHighlighter.DefaultHighlightPainter(Color(103, 91, 45))
        else:
            self.bgColor = Color(242, 246, 248)
            self.panelColor = Color(255, 255, 255)
            self.borderColor = Color(205, 216, 222)
            self.labelColor = Color(38, 58, 67)
            self.codeBgColor = Color(250, 252, 252)
            self.textColor = Color(29, 42, 48)
            self.accentColor = Color(42, 166, 151)
            self.runColor = Color(34, 139, 89)
            self.runBorderColor = Color(24, 105, 67)
            scrollThumbColor = Color(177, 191, 198)
            scrollTrackColor = Color(238, 243, 245)
            dividerColor = Color(205, 216, 222)
            gutterBgColor = Color(245, 248, 249)
            gutterTextColor = Color(91, 106, 114)
            self.painterDelete = DefaultHighlighter.DefaultHighlightPainter(Color(255, 200, 200))
            self.painterInsert = DefaultHighlighter.DefaultHighlightPainter(Color(200, 255, 200))
            self.painterReplace = DefaultHighlighter.DefaultHighlightPainter(Color(255, 240, 170))

        self.getContentPane().setBackground(self.bgColor)
        self.topPanel.setBackground(self.bgColor)
        self.themeToggle.setBackground(self.bgColor)
        self.themeToggle.setForeground(self.labelColor)
        self.themeToggle.setOpaque(True)
        self.findReplacePanel.setBackground(self.bgColor)
        for label in self.searchLabels:
            label.setForeground(self.labelColor)
            label.setBackground(self.bgColor)
            label.setOpaque(True)

        for field in (self.findField, self.replaceField):
            field.setBackground(self.codeBgColor)
            field.setForeground(self.textColor)
            field.setCaretColor(self.accentColor)
            field.setBorder(BorderFactory.createCompoundBorder(
                BorderFactory.createLineBorder(self.borderColor, 1),
                BorderFactory.createEmptyBorder(4, 6, 4, 6)
            ))

        self.runBtn.setBackground(self.runColor)
        self.runBtn.setForeground(Color(255, 255, 255))
        self.runBtn.setBorder(BorderFactory.createCompoundBorder(
            BorderFactory.createLineBorder(self.runBorderColor, 1),
            BorderFactory.createEmptyBorder(7, 14, 7, 14)
        ))
        for button in (self.findToggleBtn, self.consoleBtn, self.findBtn, self.replaceBtn, self.replaceAllBtn):
            button.setBackground(self.panelColor)
            button.setForeground(self.labelColor)
            button.setBorder(BorderFactory.createCompoundBorder(
                BorderFactory.createLineBorder(self.borderColor, 1),
                BorderFactory.createEmptyBorder(6, 10, 6, 10)
            ))
        self.addScriptBtn.setBackground(self.panelColor)
        self.addScriptBtn.setForeground(self.labelColor)
        self.addScriptBtn.setBorder(BorderFactory.createCompoundBorder(
            BorderFactory.createLineBorder(self.borderColor, 1),
            BorderFactory.createEmptyBorder(3, 8, 3, 8)
        ))
        self.removeScriptBtn.setBackground(self.panelColor)
        self.removeScriptBtn.setForeground(self.labelColor)
        self.removeScriptBtn.setBorder(BorderFactory.createCompoundBorder(
            BorderFactory.createLineBorder(self.borderColor, 1),
            BorderFactory.createEmptyBorder(3, 8, 3, 8)
        ))
        self.scriptTitlePanel.setBackground(self.panelColor)
        self.scriptControlPanel.setBackground(self.panelColor)
        self.scriptStackPanel.setBackground(self.bgColor)
        self.outputStackPanel.setBackground(self.bgColor)

        for panel in self.panePanels:
            panel.setBackground(self.panelColor)
            panel.setBorder(self.paneBorder())

        for header in self.scriptHeaders:
            header.setBackground(self.panelColor)
        for headerControls in self.scriptHeaderControls:
            headerControls.setBackground(self.panelColor)
        for header in self.outputHeaders:
            header.setBackground(self.panelColor)

        for label in self.paneLabels:
            label.setForeground(self.labelColor)
            label.setBackground(self.panelColor)
            label.setBorder(BorderFactory.createEmptyBorder(8, 10, 7, 10))

        for toggle in self.scriptToggles:
            toggle.setBackground(self.panelColor)
            toggle.setForeground(self.labelColor)
            toggle.setOpaque(True)

        for button in self.scriptCompileButtons + self.scriptTagsButtons + self.scriptRejectButtons:
            compileResult = button.getClientProperty("compileResult")
            if compileResult is True:
                button.setBackground(Color(55, 169, 104))
                button.setForeground(Color(255, 255, 255))
            elif compileResult is False:
                button.setBackground(Color(219, 83, 73))
                button.setForeground(Color(255, 255, 255))
            else:
                button.setBackground(self.panelColor)
                button.setForeground(self.labelColor)
            button.setBorder(BorderFactory.createCompoundBorder(
                BorderFactory.createLineBorder(self.borderColor, 1),
                BorderFactory.createEmptyBorder(4, 9, 4, 9)
            ))

        for area in [self.beforeArea] + self.outputAreas + self.scriptAreas:
            area.setBackground(self.codeBgColor)
            area.setForeground(self.textColor)
            area.setCaretColor(self.accentColor)
        self.refreshCompileErrorHighlights()

        if self.consoleArea is not None:
            self.consoleArea.setBackground(self.codeBgColor)
            self.consoleArea.setForeground(self.textColor)
            self.consoleArea.setCaretColor(self.accentColor)
        if self.consolePanel is not None:
            self.consolePanel.setBackground(self.bgColor)
        if self.consoleDialog is not None:
            self.consoleDialog.getContentPane().setBackground(self.bgColor)
        if self.consoleTopPanel is not None:
            self.consoleTopPanel.setBackground(self.bgColor)
        if self.consoleScrollPane is not None:
            self.consoleScrollPane.setBorder(BorderFactory.createMatteBorder(1, 0, 0, 0, self.borderColor))
            self.consoleScrollPane.getViewport().setBackground(self.codeBgColor)
            self.applyScrollBarTheme(self.consoleScrollPane, scrollThumbColor, scrollTrackColor)
        if self.consoleClearBtn is not None:
            self.consoleClearBtn.setBackground(self.panelColor)
            self.consoleClearBtn.setForeground(self.labelColor)
            self.consoleClearBtn.setBorder(BorderFactory.createCompoundBorder(
                BorderFactory.createLineBorder(self.borderColor, 1),
                BorderFactory.createEmptyBorder(6, 10, 6, 10)
            ))

        for scrollPane in self.scrollPanes:
            scrollPane.setBorder(BorderFactory.createMatteBorder(1, 0, 0, 0, self.borderColor))
            scrollPane.getViewport().setBackground(self.codeBgColor)
            self.applyScrollBarTheme(scrollPane, scrollThumbColor, scrollTrackColor)

        self.applyScriptGutterTheme(gutterBgColor, gutterTextColor)

        for splitPane in self.splitPanes:
            self.applySplitPaneTheme(splitPane, dividerColor)

        self.clearHighlights()
        self.repaint()

    def applyScrollBarTheme(self, scrollPane, thumbColor, trackColor):
        for scrollBar in (scrollPane.getVerticalScrollBar(), scrollPane.getHorizontalScrollBar()):
            if scrollBar is not None:
                scrollBar.setUI(FlatScrollBarUI(thumbColor, trackColor))
                scrollBar.setBackground(trackColor)
                scrollBar.setForeground(thumbColor)
                scrollBar.setUnitIncrement(16)

    def applyScriptGutterTheme(self, bgColor, textColor):
        for scrollPane in self.scriptScrollPanes:
            try:
                gutter = scrollPane.getGutter()
                gutter.setBackground(bgColor)
                gutter.setLineNumberColor(textColor)
                gutter.setBorderColor(self.borderColor)
                gutter.setLineNumberFont(self.textFont)
            except Exception:
                pass

    def applySplitPaneTheme(self, splitPane, dividerColor):
        splitPane.setBackground(self.bgColor)
        splitPane.setBorder(BorderFactory.createEmptyBorder())
        try:
            divider = splitPane.getUI().getDivider()
            divider.setBackground(dividerColor)
            divider.setBorder(BorderFactory.createLineBorder(dividerColor, 1))
        except Exception:
            pass

    def onThemeToggle(self):
        self.darkMode = self.themeToggle.isSelected()
        self.preferences.putBoolean("darkMode", self.darkMode)
        self.applyTheme(self.darkMode)

    def showConsole(self):
        if self.consoleDialog is not None and self.consoleDialog.isVisible():
            self.consoleDialog.setVisible(False)
            return
        if self.consoleDialog is None:
            self.consoleDialog = JDialog()
            self.consoleDialog.setTitle("Console Output")
            self.consoleDialog.setModal(False)
            self.consoleDialog.setAlwaysOnTop(False)
            self.consoleDialog.setDefaultCloseOperation(JDialog.HIDE_ON_CLOSE)
            self.consoleDialog.setPreferredSize(Dimension(850, 360))
            panel = JPanel(BorderLayout())
            self.consolePanel = panel
            self.consoleArea = JTextArea()
            self.consoleArea.setEditable(False)
            self.consoleArea.setLineWrap(False)
            self.consoleArea.setFont(self.textFont)
            self.consoleArea.setMargin(Insets(10, 10, 10, 10))
            self.consoleArea.setText(self.consoleBuffer)
            self.consoleScrollPane = self.cleanScrollPane(self.consoleArea)
            self.consoleClearBtn = self.toolbarButton("Clear")
            self.consoleClearBtn.addActionListener(lambda e: self.clearConsole())
            self.consoleTopPanel = JPanel()
            self.consoleTopPanel.add(self.consoleClearBtn)
            panel.add(self.consoleTopPanel, BorderLayout.NORTH)
            panel.add(self.consoleScrollPane, BorderLayout.CENTER)
            self.consoleDialog.getContentPane().add(panel)
            self.consoleDialog.pack()
            self.consoleDialog.setLocationRelativeTo(self)
            self.applyTheme(self.themeToggle.isSelected())
        self.consoleDialog.setVisible(True)

    def appendConsoleOutput(self, label, output):
        if output is None or output == "":
            return
        header = "\n[%s]\n" % label
        if self.consoleBuffer:
            self.consoleBuffer += header + output
        else:
            self.consoleBuffer = header.lstrip() + output
        if self.consoleArea is not None:
            self.consoleArea.setText(self.consoleBuffer)
            self.consoleArea.setCaretPosition(len(self.consoleArea.getText()))

    def clearConsole(self):
        self.consoleBuffer = ""
        if self.consoleArea is not None:
            self.consoleArea.setText("")

    def startConsoleCapture(self):
        buffer = StringIO()
        capture = (sys.stdout, sys.stderr, buffer)
        sys.stdout = buffer
        sys.stderr = buffer
        return capture

    def finishConsoleCapture(self, capture, label):
        old_stdout, old_stderr, buffer = capture
        sys.stdout = old_stdout
        sys.stderr = old_stderr
        self.appendConsoleOutput(label, buffer.getvalue())

    def compileScriptForButton(self, button):
        try:
            idx = self.scriptCompileButtons.index(button)
        except ValueError:
            return
        self.compileScript(idx)

    def compileScript(self, idx):
        button = self.scriptCompileButtons[idx]
        area = self.scriptAreas[idx]
        script = self.scriptAreas[idx].getText()
        self.clearCompileErrorHighlight(area)
        if not script.strip():
            self.setCompileStatus(button, False, "Script is empty.")
            return False
        try:
            compile(script, '<inline_script_%d>' % (idx + 1), 'exec')
            self.setCompileStatus(button, True, "Jython Script %d syntax is valid." % (idx + 1))
            return True
        except Exception:
            errorText = traceback.format_exc()
            self.setCompileStatus(button, False, errorText)
            self.highlightCompileError(area, errorText)
            return False

    def setCompileStatus(self, button, success, tooltip):
        button.putClientProperty("compileResult", success)
        if success:
            button.setBackground(Color(55, 169, 104))
            button.setForeground(Color(255, 255, 255))
        else:
            button.setBackground(Color(219, 83, 73))
            button.setForeground(Color(255, 255, 255))
        button.setToolTipText(tooltip)

    def resetCompileButton(self, area, button):
        button.putClientProperty("compileResult", None)
        button.setBackground(self.panelColor)
        button.setForeground(self.labelColor)
        button.setToolTipText(None)
        self.clearCompileErrorHighlight(area)

    def compileErrorLineNumber(self, errorText):
        matches = re.findall(r'File ".*?", line (\d+)', errorText)
        if matches:
            try:
                return int(matches[-1])
            except Exception:
                return None
        return None

    def highlightCompileError(self, area, errorText):
        lineNumber = self.compileErrorLineNumber(errorText)
        if lineNumber is None:
            return
        lineIndex = lineNumber - 1
        self.addCompileErrorHighlight(area, lineIndex, errorText)

    def addCompileErrorHighlight(self, area, lineIndex, errorText):
        try:
            if self.themeToggle.isSelected():
                color = Color(103, 50, 55)
            else:
                color = Color(255, 205, 205)
            tag = area.addLineHighlight(lineIndex, color)
            self.scriptCompileErrorHighlights[area] = [tag]
            self.scriptCompileErrorLines[area] = {lineIndex: errorText}
        except Exception:
            pass

    def refreshCompileErrorHighlights(self):
        for area in self.scriptAreas:
            errorLines = self.scriptCompileErrorLines.get(area, {})
            if not errorLines:
                continue
            for tag in self.scriptCompileErrorHighlights.get(area, []):
                try:
                    area.removeLineHighlight(tag)
                except Exception:
                    pass
            self.scriptCompileErrorHighlights[area] = []
            for lineIndex in errorLines.keys():
                self.addCompileErrorHighlight(area, lineIndex, errorLines[lineIndex])

    def clearCompileErrorHighlight(self, area):
        try:
            for tag in self.scriptCompileErrorHighlights.get(area, []):
                try:
                    area.removeLineHighlight(tag)
                except Exception:
                    pass
        except Exception:
            pass
        self.scriptCompileErrorHighlights[area] = []
        self.scriptCompileErrorLines[area] = {}
        area.setToolTipText(" ")

    def updateScriptErrorToolTip(self, area, event):
        errorLines = self.scriptCompileErrorLines.get(area, {})
        if not errorLines:
            area.setToolTipText(" ")
            return
        try:
            offset = area.viewToModel(event.getPoint())
            line = area.getLineOfOffset(offset)
            if errorLines.has_key(line):
                area.setToolTipText("<html><pre>%s</pre></html>" % self.escapeHtml(errorLines[line]))
            else:
                area.setToolTipText(" ")
        except Exception:
            area.setToolTipText(" ")

    def escapeHtml(self, text):
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    def testIsRejectedForButton(self, button):
        try:
            idx = self.scriptRejectButtons.index(button)
        except ValueError:
            return
        self.testIsRejected(idx)

    def testGetTagsForButton(self, button):
        try:
            idx = self.scriptTagsButtons.index(button)
        except ValueError:
            return
        self.testGetTags(idx)

    def testGetTags(self, idx):
        try:
            stageInput = self.inputForScript(idx)
            context = self.defaultContext()
            ns = self.loadScriptNamespace(idx, stageInput, context)
            tags = self.evaluateGetTags(idx, stageInput, context, ns)
            self.showMessage("getTags Result", "tags=%s" % tags)
        except Exception:
            self.showError("Error during getTags test:\n%s" % traceback.format_exc())

    def testIsRejected(self, idx):
        try:
            stageInput = self.inputForScript(idx)
            context = self.defaultContext()
            ns = self.loadScriptNamespace(idx, stageInput, context)
            fn = ns.get('isRejected')
            if fn is None or not callable(fn):
                self.showMessage("isRejected Test", "Jython Script %d does not define isRejected(inString, context)." % (idx + 1))
                return

            self.evaluateGetTags(idx, stageInput, context, ns)
            capture = self.startConsoleCapture()
            try:
                result = fn(stageInput, context)
            finally:
                self.finishConsoleCapture(capture, "Jython Script %d isRejected" % (idx + 1))
            isRejected = bool(result)
            message = "isRejected=%s" % isRejected
            if isRejected and context.get('rejectReason'):
                message += "\nrejectReason=%s" % context.get('rejectReason')
            self.showMessage("isRejected Test", message)
        except Exception:
            self.showError("Error during isRejected test:\n%s" % traceback.format_exc())

    def defaultContext(self):
        return {'tags': []}

    def loadScriptNamespace(self, idx, inString, context=None):
        script = self.scriptAreas[idx].getText()
        if not script.strip():
            raise Exception("Jython Script %d is empty." % (idx + 1))
        if context is None:
            context = self.defaultContext()
        elif not context.has_key('tags'):
            context['tags'] = []
        ns = {'inString': inString, 'context': context}
        codeName = self.scriptPath if idx == 0 and self.scriptPath else '<inline_script_%d>' % (idx + 1)
        capture = self.startConsoleCapture()
        try:
            code = compile(script, codeName, 'exec')
            exec(code, ns, ns)
        finally:
            self.finishConsoleCapture(capture, "Jython Script %d load" % (idx + 1))
        return ns

    def evaluateGetTags(self, idx, inString, context, ns):
        if not context.has_key('tags'):
            context['tags'] = []
        fn = ns.get('getTags')
        if fn is None or not callable(fn):
            return context['tags']
        capture = self.startConsoleCapture()
        try:
            tags = fn(inString, context)
        finally:
            self.finishConsoleCapture(capture, "Jython Script %d getTags" % (idx + 1))
        if tags is None:
            tags = context.get('tags', [])
        context['tags'] = tags
        return tags

    def inputForScript(self, targetIdx):
        resultText = self.beforeArea.getText()
        for idx in range(targetIdx):
            if not self.scriptToggles[idx].isSelected():
                continue
            resultText = self.runProcessScript(idx, resultText)
        return resultText

    def runProcessScript(self, idx, inString):
        context = self.defaultContext()
        ns = self.loadScriptNamespace(idx, inString, context)
        self.evaluateGetTags(idx, inString, context, ns)
        fn = ns.get('process')
        if fn is None or not callable(fn):
            fn = ns.get('transform')
        if fn is None or not callable(fn):
            return inString

        capture = self.startConsoleCapture()
        try:
            result = fn(inString)
        finally:
            self.finishConsoleCapture(capture, "Jython Script %d process" % (idx + 1))
        if result is None:
            raise Exception("Jython Script %d returned None; expected a string." % (idx + 1))

        try:
            basestring  # Jython 2.7 compatibility
            is_text = isinstance(result, basestring)
        except NameError:
            is_text = isinstance(result, str)
        if not is_text:
            result = str(result)
        return result

    def installSearchShortcuts(self):
        root = self.getRootPane()
        inputMap = root.getInputMap(JComponent.WHEN_IN_FOCUSED_WINDOW)
        actionMap = root.getActionMap()

        inputMap.put(KeyStroke.getKeyStroke(KeyEvent.VK_F, InputEvent.CTRL_DOWN_MASK), "focusFind")
        actionMap.put("focusFind", ShortcutAction(self.focusFind))

        inputMap.put(KeyStroke.getKeyStroke(KeyEvent.VK_H, InputEvent.CTRL_DOWN_MASK), "focusReplace")
        actionMap.put("focusReplace", ShortcutAction(self.focusReplace))

        inputMap.put(KeyStroke.getKeyStroke(KeyEvent.VK_F3, 0), "findNext")
        actionMap.put("findNext", ShortcutAction(lambda: self.findNext(False)))

        inputMap.put(KeyStroke.getKeyStroke(KeyEvent.VK_F3, InputEvent.SHIFT_DOWN_MASK), "findPrevious")
        actionMap.put("findPrevious", ShortcutAction(lambda: self.findNext(True)))

        inputMap.put(KeyStroke.getKeyStroke(KeyEvent.VK_R, InputEvent.CTRL_DOWN_MASK), "replaceCurrent")
        actionMap.put("replaceCurrent", ShortcutAction(self.replaceCurrent))

        inputMap.put(KeyStroke.getKeyStroke(KeyEvent.VK_Z, InputEvent.CTRL_DOWN_MASK), "undoEdit")
        actionMap.put("undoEdit", ShortcutAction(self.undoCurrentTextArea))

        inputMap.put(KeyStroke.getKeyStroke(KeyEvent.VK_Y, InputEvent.CTRL_DOWN_MASK), "redoEdit")
        actionMap.put("redoEdit", ShortcutAction(self.redoCurrentTextArea))

        inputMap.put(KeyStroke.getKeyStroke(KeyEvent.VK_Z, InputEvent.CTRL_DOWN_MASK | InputEvent.SHIFT_DOWN_MASK), "redoEdit")

    def focusFind(self):
        self.showFindReplace()
        selected = self.getActiveSelectedText()
        if selected:
            self.findField.setText(selected)
        self.findField.requestFocusInWindow()
        self.findField.selectAll()

    def focusReplace(self):
        self.showFindReplace()
        self.replaceField.requestFocusInWindow()
        self.replaceField.selectAll()

    def showFindReplace(self):
        if not self.findReplacePanel.isVisible():
            self.findReplacePanel.setVisible(True)
            self.topPanel.revalidate()
            self.topPanel.repaint()

    def toggleFindReplace(self):
        self.findReplacePanel.setVisible(not self.findReplacePanel.isVisible())
        self.topPanel.revalidate()
        self.topPanel.repaint()
        if self.findReplacePanel.isVisible():
            self.focusFind()

    def getActiveSelectedText(self):
        area = self.currentTextArea()
        if area is None:
            return None
        selected = area.getSelectedText()
        if selected is None or selected == "":
            return None
        return selected

    def currentTextArea(self):
        owner = KeyboardFocusManager.getCurrentKeyboardFocusManager().getFocusOwner()
        if isinstance(owner, JTextComponent) and owner not in (self.findField, self.replaceField):
            self.activeTextArea = owner
        return self.activeTextArea

    def currentEditableTextArea(self):
        owner = KeyboardFocusManager.getCurrentKeyboardFocusManager().getFocusOwner()
        if owner in (self.findField, self.replaceField):
            return None
        if isinstance(owner, JTextComponent):
            self.activeTextArea = owner
        area = self.activeTextArea
        if area is None or not area.isEditable():
            return None
        return area

    def undoCurrentTextArea(self):
        area = self.currentEditableTextArea()
        if area is None:
            return
        manager = self.undoManagers.get(area)
        if manager is not None and manager.canUndo():
            try:
                manager.undo()
            except Exception:
                pass

    def redoCurrentTextArea(self):
        area = self.currentEditableTextArea()
        if area is None:
            return
        manager = self.undoManagers.get(area)
        if manager is not None and manager.canRedo():
            try:
                manager.redo()
            except Exception:
                pass

    def findNext(self, reverse=False):
        area = self.currentTextArea()
        needle = self.findField.getText()
        if area is None or not needle:
            return False

        text = area.getText()
        if not text:
            return False

        haystack = text.lower()
        query = needle.lower()
        if reverse:
            start = max(0, area.getSelectionStart() - 1)
            pos = haystack.rfind(query, 0, start + 1)
            if pos < 0:
                pos = haystack.rfind(query)
        else:
            start = area.getSelectionEnd()
            pos = haystack.find(query, start)
            if pos < 0:
                pos = haystack.find(query)

        if pos < 0:
            return False

        area.requestFocusInWindow()
        area.select(pos, pos + len(needle))
        return True

    def selectedTextMatchesFind(self, area):
        selected = area.getSelectedText()
        needle = self.findField.getText()
        return selected is not None and needle and selected.lower() == needle.lower()

    def replaceCurrent(self):
        area = self.currentTextArea()
        if area is None or not self.findField.getText():
            return
        if not area.isEditable():
            self.showError("Replace is only available in editable panes.")
            return

        if not self.selectedTextMatchesFind(area):
            if not self.findNext(False):
                return

        if self.selectedTextMatchesFind(area):
            area.replaceSelection(self.replaceField.getText())
            self.findNext(False)

    def replaceAll(self):
        area = self.currentTextArea()
        needle = self.findField.getText()
        replacement = self.replaceField.getText()
        if area is None or not needle:
            return
        if not area.isEditable():
            self.showError("Replace All is only available in editable panes.")
            return

        text = area.getText()
        lowerText = text.lower()
        lowerNeedle = needle.lower()
        pieces = []
        pos = 0
        count = 0
        while True:
            found = lowerText.find(lowerNeedle, pos)
            if found < 0:
                pieces.append(text[pos:])
                break
            pieces.append(text[pos:found])
            pieces.append(replacement)
            pos = found + len(needle)
            count += 1

        if count:
            area.setText(''.join(pieces))
            area.setCaretPosition(0)

    def default_script_template(self, scriptNumber=1):
        return (
            "# Jython process script %d\n" % scriptNumber +
            "# Define process(inString) -> string\n"
            "def process(inString):\n"
            "    return inString\n"
        )

    def onLoadHL7(self, event):
        chooser = JFileChooser()
        if chooser.showOpenDialog(self) == JFileChooser.APPROVE_OPTION:
            try:
                content = read_file(chooser.getSelectedFile().getAbsolutePath())
                self.beforeArea.setText(content)
                self.clearHighlights()
            except Exception as e:
                self.showError("Failed to load HL7: %s" % e)

    def onSaveHL7(self, event):
        chooser = JFileChooser()
        if chooser.showSaveDialog(self) == JFileChooser.APPROVE_OPTION:
            try:
                write_file(chooser.getSelectedFile().getAbsolutePath(), self.beforeArea.getText())
            except Exception as e:
                self.showError("Failed to save HL7: %s" % e)

    def onLoadScript(self, event):
        chooser = JFileChooser()
        if chooser.showOpenDialog(self) == JFileChooser.APPROVE_OPTION:
            try:
                path = chooser.getSelectedFile().getAbsolutePath()
                content = read_file(path)
                self.scriptAreas[0].setText(content)
                self.scriptPath = path
            except Exception as e:
                self.showError("Failed to load script: %s" % e)

    def onSaveScript(self, event):
        chooser = JFileChooser()
        if chooser.showSaveDialog(self) == JFileChooser.APPROVE_OPTION:
            try:
                path = chooser.getSelectedFile().getAbsolutePath()
                write_file(path, self.scriptAreas[0].getText())
                self.scriptPath = path
            except Exception as e:
                self.showError("Failed to save script: %s" % e)

    def onSaveOutput(self, event):
        chooser = JFileChooser()
        if chooser.showSaveDialog(self) == JFileChooser.APPROVE_OPTION:
            try:
                write_file(chooser.getSelectedFile().getAbsolutePath(), self.afterArea.getText())
            except Exception as e:
                self.showError("Failed to save output: %s" % e)

    def onRun(self, event):
        self.runPipeline(True)

    def onScriptToggle(self):
        if self.beforeArea.getText().strip():
            self.runPipeline(True)

    def runPipeline(self, showErrors):
        inString = self.beforeArea.getText()
        resultText = inString
        currentScriptIndex = 0
        try:
            for idx, scriptArea in enumerate(self.scriptAreas):
                currentScriptIndex = idx
                if not self.scriptToggles[idx].isSelected():
                    self.outputAreas[idx].setText(resultText)
                    continue

                script = scriptArea.getText()
                if not script.strip():
                    if showErrors:
                        self.showError("Jython Script %d is enabled but empty." % (idx + 1))
                    self.clearOutputAreasFrom(idx)
                    return

                resultText = self.runProcessScript(idx, resultText)
                self.outputAreas[idx].setText(resultText)

            self.afterArea.setText(resultText)
            self.applyDiffHighlightsHL7Sections()
        except Exception:
            self.clearOutputAreasFrom(currentScriptIndex)
            if showErrors:
                tb = traceback.format_exc()
                self.showError("Error during process/transform:\n%s" % tb)

    def clearOutputAreasFrom(self, startIndex):
        for idx in range(startIndex, len(self.outputAreas)):
            self.outputAreas[idx].setText("")

    # -----------------------
    # Diff helpers (HL7 section-aware per line, ignoring line-ending differences)
    # -----------------------
    def clearHighlights(self):
        self.beforeArea.getHighlighter().removeAllHighlights()
        for area in self.outputAreas:
            area.getHighlighter().removeAllHighlights()

    def split_lines_with_offsets(self, text):
        """
        Split text into lines, treating \\r, \\n, and \\r\\n as line terminators.
        Returns:
          - lines: list of line strings without their EOLs
          - offsets: list of absolute start offsets for each line; plus a sentinel at end (len(text))
        This allows us to ignore differences in line-ending styles during comparison/highlighting.
        """
        lines = []
        offsets = []
        i = 0
        start = 0
        n = len(text)
        while i < n:
            ch = text[i]
            if ch == '\r':
                # line from start to i (without CR)
                lines.append(text[start:i])
                offsets.append(start)
                # handle CRLF
                if i + 1 < n and text[i + 1] == '\n':
                    i += 2
                else:
                    i += 1
                start = i
                continue
            elif ch == '\n':
                # line from start to i (without LF)
                lines.append(text[start:i])
                offsets.append(start)
                i += 1
                start = i
                continue
            else:
                i += 1
        # last line (even if empty)
        lines.append(text[start:n])
        offsets.append(start)
        # sentinel end
        offsets.append(n)
        return lines, offsets

    def tokenize_hl7_with_offsets(self, line):
        """
        Split a line into tokens while keeping delimiters | ^ & as separate tokens.
        Returns (tokens, spans) where spans[i] = (start, end) char offsets of tokens[i].
        """
        tokens = self.hl7_split_regex.split(line)
        spans = []
        pos = 0
        for tok in tokens:
            start = pos
            end = pos + len(tok)
            spans.append((start, end))
            pos = end
        return tokens, spans

    def applyDiffHighlightsHL7Sections(self):
        """
        For each pair of lines by index:
          - Split lines using split_lines_with_offsets (ignores EOL differences).
          - Tokenize both lines on | ^ & (keeping delimiters).
          - Compare token-by-token; within non-delimiter tokens, highlight only differing subranges.
          - Extra tokens on one side are highlighted fully on that side.
        """
        self.clearHighlights()

        before_text = self.beforeArea.getText()
        after_text = self.afterArea.getText()

        before_lines, before_offsets = self.split_lines_with_offsets(before_text)
        after_lines, after_offsets = self.split_lines_with_offsets(after_text)

        hl_before = self.beforeArea.getHighlighter()
        hl_after = self.afterArea.getHighlighter()

        max_lines = max(len(before_lines), len(after_lines))

        for idx in range(max_lines):
            b_line = before_lines[idx] if idx < len(before_lines) else None
            a_line = after_lines[idx] if idx < len(after_lines) else None

            # Only on one side -> highlight the entire line on that side
            if b_line is None and a_line is not None:
                a_start = after_offsets[idx]
                a_end = after_offsets[idx + 1]
                try:
                    hl_after.addHighlight(a_start, a_end, self.painterInsert)
                except Exception:
                    pass
                continue

            if a_line is None and b_line is not None:
                b_start = before_offsets[idx]
                b_end = before_offsets[idx + 1]
                try:
                    hl_before.addHighlight(b_start, b_end, self.painterDelete)
                except Exception:
                    pass
                continue

            # Both exist; if exactly equal, skip
            if b_line == a_line:
                continue

            # Tokenize both lines, keeping delimiters
            b_tokens, b_spans = self.tokenize_hl7_with_offsets(b_line)
            a_tokens, a_spans = self.tokenize_hl7_with_offsets(a_line)

            # Compare token-by-token
            max_tok = max(len(b_tokens), len(a_tokens))
            for t in range(max_tok):
                b_tok = b_tokens[t] if t < len(b_tokens) else None
                a_tok = a_tokens[t] if t < len(a_tokens) else None

                # Token exists only on one side
                if b_tok is None and a_tok is not None:
                    a_start_rel, a_end_rel = a_spans[t]
                    try:
                        hl_after.addHighlight(after_offsets[idx] + a_start_rel, after_offsets[idx] + a_end_rel, self.painterInsert)
                    except Exception:
                        pass
                    continue

                if a_tok is None and b_tok is not None:
                    b_start_rel, b_end_rel = b_spans[t]
                    try:
                        hl_before.addHighlight(before_offsets[idx] + b_start_rel, before_offsets[idx] + b_end_rel, self.painterDelete)
                    except Exception:
                        pass
                    continue

                # Both tokens exist and are equal
                if b_tok == a_tok:
                    continue

                # Non-delimiter tokens: highlight only differing subrange
                if b_tok not in ('|', '^', '&') and a_tok not in ('|', '^', '&'):
                    prefix = 0
                    min_len = min(len(b_tok), len(a_tok))
                    while prefix < min_len and b_tok[prefix] == a_tok[prefix]:
                        prefix += 1

                    suffix = 0
                    while (suffix < (len(b_tok) - prefix)) and (suffix < (len(a_tok) - prefix)) and \
                          b_tok[len(b_tok) - 1 - suffix] == a_tok[len(a_tok) - 1 - suffix]:
                        suffix += 1

                    # Before token differing slice
                    b_start_rel, b_end_rel = b_spans[t]
                    b_s = b_start_rel + prefix
                    b_e = b_end_rel - suffix
                    if b_s < b_e:
                        try:
                            hl_before.addHighlight(before_offsets[idx] + b_s, before_offsets[idx] + b_e, self.painterReplace)
                        except Exception:
                            pass

                    # After token differing slice
                    a_start_rel, a_end_rel = a_spans[t]
                    a_s = a_start_rel + prefix
                    a_e = a_end_rel - suffix
                    if a_s < a_e:
                        try:
                            hl_after.addHighlight(after_offsets[idx] + a_s, after_offsets[idx] + a_e, self.painterReplace)
                        except Exception:
                            pass
                else:
                    # Delimiter token changed — highlight whole delimiter
                    b_start_rel, b_end_rel = b_spans[t]
                    a_start_rel, a_end_rel = a_spans[t]
                    try:
                        hl_before.addHighlight(before_offsets[idx] + b_start_rel, before_offsets[idx] + b_end_rel, self.painterReplace)
                    except Exception:
                        pass
                    try:
                        hl_after.addHighlight(after_offsets[idx] + a_start_rel, after_offsets[idx] + a_end_rel, self.painterReplace)
                    except Exception:
                        pass

    def showError(self, msg):
        JOptionPane.showMessageDialog(self, msg, "Error", JOptionPane.ERROR_MESSAGE)

    def showInfo(self, msg):
        self.showMessage("Info", msg)

    def showMessage(self, title, msg):
        JOptionPane.showMessageDialog(self, msg, title, JOptionPane.INFORMATION_MESSAGE)


def main():
    SwingUtilities.invokeLater(lambda: HL7TransformGUI().setVisible(True))


if __name__ == '__main__':
    main()
