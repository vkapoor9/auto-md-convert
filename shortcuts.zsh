# AutoMDConvert shell shortcuts
#
# Source this from your ~/.zshrc (use your actual clone path):
#   source /path/to/auto-md-convert/shortcuts.zsh
#
# Then, from any directory:
#   add-folder <path>      enable a folder (watches <path>/emails)
#   list-folder            show watched folders
#   remove-folder <path>   disable a folder

# Resolve this file's own directory so the shortcuts work from any install location.
_AUTOMDCONVERT_DIR="${${(%):-%x}:A:h}"

add-folder()    { python3 "$_AUTOMDCONVERT_DIR/dropzone/watch_folder.py" add "$@"; }
remove-folder() { python3 "$_AUTOMDCONVERT_DIR/dropzone/watch_folder.py" remove "$@"; }
list-folder()   { python3 "$_AUTOMDCONVERT_DIR/dropzone/watch_folder.py" list; }
