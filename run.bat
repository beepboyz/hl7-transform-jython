@echo off
setlocal enabledelayedexpansion
cd /d %~dp0

set JYTHON_JAR=jython-standalone-2.7.3.jar
set CLASSPATH=%JYTHON_JAR%;lib\*
set LOG_FILE=hl7_transform_gui.log

start "" javaw -cp "%CLASSPATH%" org.python.util.jython launch_gui.py > "%LOG_FILE%" 2>&1
