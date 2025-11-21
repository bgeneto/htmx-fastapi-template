#!/usr/bin/env bash
# Translation management script for i18n

set -e

# Colors for output
GREEN='\033[0;32m'
BLUE='\033[0;34m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

TRANSLATIONS_DIR="translations"
POT_FILE="messages.pot"

echo -e "${BLUE}=== Translation Management Script ===${NC}\n"

# Function to extract messages
extract() {
    echo -e "${YELLOW}→${NC} Extracting translatable messages..."
    pybabel extract -F babel.cfg -o "$POT_FILE" . --project=alpine-fastapi-app
    echo -e "${GREEN}✓${NC} Messages extracted to $POT_FILE\n"
}

# Function to initialize a new locale
init() {
    local locale="$1"
    if [ -z "$locale" ]; then
        echo "Usage: $0 init <locale>"
        echo "Example: $0 init pt_BR"
        exit 1
    fi

    echo -e "${YELLOW}→${NC} Initializing locale: $locale"
    pybabel init -i "$POT_FILE" -d "$TRANSLATIONS_DIR" -l "$locale"
    echo -e "${GREEN}✓${NC} Locale $locale initialized\n"
}

# Function to update existing translations
update() {
    echo -e "${YELLOW}→${NC} Updating existing translations..."
    pybabel update -i "$POT_FILE" -d "$TRANSLATIONS_DIR"
    echo -e "${GREEN}✓${NC} Translations updated\n"
}

# Function to compile translations
compile() {
    echo -e "${YELLOW}→${NC} Compiling translations..."
    pybabel compile -d "$TRANSLATIONS_DIR"
    echo -e "${GREEN}✓${NC} Translations compiled\n"
}

# Function to list available locales
list() {
    echo -e "${YELLOW}→${NC} Available locales:"
    if [ -d "$TRANSLATIONS_DIR" ]; then
        for dir in "$TRANSLATIONS_DIR"/*/ ; do
            if [ -d "$dir" ]; then
                locale=$(basename "$dir")
                echo "  - $locale"
            fi
        done
    else
        echo "  (none found)"
    fi
    echo ""
}

# Main command handling
case "${1:-help}" in
    extract)
        extract
        ;;
    init)
        extract
        init "$2"
        ;;
    update)
        extract
        update
        ;;
    compile)
        compile
        ;;
    refresh)
        extract
        update
        compile
        echo -e "${GREEN}✓✓✓${NC} All translations refreshed and compiled!"
        ;;
    list)
        list
        ;;
    help|*)
        echo "Usage: $0 {extract|init|update|compile|refresh|list} [options]"
        echo ""
        echo "Commands:"
        echo "  extract           Extract messages from source code"
        echo "  init <locale>     Initialize a new locale (e.g., pt_BR)"
        echo "  update            Update existing translations with new messages"
        echo "  compile           Compile .po files to .mo files"
        echo "  refresh           Extract, update, and compile in one step"
        echo "  list              List available locales"
        echo ""
        echo "Examples:"
        echo "  $0 init pt_BR              # Create Portuguese (Brazil) translation"
        echo "  $0 init es                 # Create Spanish translation"
        echo "  $0 refresh                 # Update and compile all translations"
        echo ""
        ;;
esac
