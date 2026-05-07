#!/usr/bin/env bash
set -euo pipefail
DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$DIR"

JYTHON_JAR="${JYTHON_JAR:-jython-standalone-2.7.3.jar}"
CLASSPATH="$JYTHON_JAR:lib/*"

exec java -cp "$CLASSPATH" org.python.util.jython hl7_transform_gui.py