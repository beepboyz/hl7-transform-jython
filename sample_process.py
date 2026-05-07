# Example Jython script compatible with the GUI.
# It defines process(inString) and uses LightHL7 if available.
# Adjust imports to your LightHL7 jar/package versions.
from org.nule.lighthl7lib.hl7 import Hl7Record

def process(inString):
    # Ensure carriage returns for HL7 segment delimiters
    msg = inString.replace('\n', '\r')

    # Parse and modify via LightHL7
    inMessage = Hl7Record(msg)
    msh = inMessage.getSegment('MSH')
    if msh is not None:
        # Example: set MSH-6 (Receiving Facility)
        msh.field(6).changeField('BWH')
        msh.rebuild()

    # Example: append a custom NTE at end
    inMessage.append('NTE')
    inMessage.get(inMessage.size()).changeSegment('NTE|1||Processed by sample_process.py')

    # Return rebuilt HL7 text
    return inMessage.rebuild()