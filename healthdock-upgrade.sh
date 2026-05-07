#!/usr/bin/env bash
set -euo pipefail

APP_USER="healthdock"
APP_HOME="/home/healthdock"
BACKUP_DIR="$APP_HOME/healthdock-backup"
WAR_DIR="$APP_HOME/war"
TOMCAT_DIR="$APP_HOME/tomcat"
DOWNLOAD_BASE_URL="http://cernhhbcds04/cdsng"

usage() {
  cat <<USAGE
Usage:
  $0 <version> [--dry-run]

Example:
  $0 4.2968.0
  $0 4.2968.0 --dry-run

This downloads healthdock-<version>.war, stops Tomcat, clears the deployed app
and Tomcat temp/work directories, unzips the WAR, then starts HealthDock.
USAGE
}

run() {
  echo "+ $*"
  if [[ "${DRY_RUN:-false}" != "true" ]]; then
    "$@"
  fi
}

run_tomcat_stop() {
  echo "+ $TOMCAT_DIR/bin/service.sh stop"
  if [[ "$DRY_RUN" == "true" ]]; then
    return 0
  fi

  set +e
  "$TOMCAT_DIR/bin/service.sh" stop
  stop_rc=$?
  set -e

  if [[ "$stop_rc" -ne 0 ]]; then
    echo "Tomcat stop returned RC=$stop_rc; continuing because some installs return non-zero after stopping cleanly."
  fi
}

VERSION="${1:-}"
DRY_RUN="false"

if [[ -z "$VERSION" || "$VERSION" == "-h" || "$VERSION" == "--help" ]]; then
  usage
  exit 0
fi

if [[ "${2:-}" == "--dry-run" ]]; then
  DRY_RUN="true"
elif [[ -n "${2:-}" ]]; then
  echo "Unknown argument: $2" >&2
  usage
  exit 1
fi

if [[ "$(id -un)" != "$APP_USER" ]]; then
  echo "Run this as the $APP_USER user." >&2
  exit 1
fi

WAR_FILE="healthdock-$VERSION.war"
DOWNLOAD_URL="$DOWNLOAD_BASE_URL/$WAR_FILE"
LOCAL_WAR="$BACKUP_DIR/$WAR_FILE"

for dir in "$BACKUP_DIR" "$WAR_DIR" "$TOMCAT_DIR" "$TOMCAT_DIR/bin"; do
  if [[ ! -d "$dir" ]]; then
    echo "Expected directory does not exist: $dir" >&2
    exit 1
  fi
done

echo "Preparing to deploy $WAR_FILE"
echo "Source: $DOWNLOAD_URL"
echo "Target: $WAR_DIR"

if [[ "$DRY_RUN" != "true" ]]; then
  read -r -p "Continue? [y/N] " confirm
  case "$confirm" in
    y|Y|yes|YES) ;;
    *) echo "Canceled."; exit 0 ;;
  esac
fi

run curl -fL --retry 3 --retry-delay 5 -o "$LOCAL_WAR" "$DOWNLOAD_URL"
run chown "$APP_USER:$APP_USER" "$LOCAL_WAR"

run_tomcat_stop

run rm -rf "$WAR_DIR"/* "$TOMCAT_DIR/temp"/* "$TOMCAT_DIR/work"/*

run unzip -q "$LOCAL_WAR" -d "$WAR_DIR"

run bash "$APP_HOME/auto-restart.sh"

echo "Deployment complete: $WAR_FILE"
