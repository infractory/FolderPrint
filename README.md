# FolderPrint
## Purpose
This script is meant to automatically print files using Cups when put into some directory.
It can also convert files into PDF before printing them.

## Dependencies
- libreoffice (or equivalent)
- Cups
- python modules:
  - ruamel-yaml
  - pyyaml
  - pycups
  - argcomplete

## Two printing modes are available
### Direct Printing
When a file is uploaded into a printing directory, it is printed.
### Delayed Printing
When a file is uploaded into a printing directory, the printing job is put on hold until the user unblock the job by connecting to a printer to ask for printing this job on that printer.
