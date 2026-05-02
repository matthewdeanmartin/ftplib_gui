# FTPLib GUI

FTPLib GUI is a desktop FTP and FTPS client built with Tkinter on top of Python's standard-library
`ftplib`. It gives you a graphical way to connect to servers, browse local and remote directories,
queue transfers, and manage saved connection profiles without dropping to a raw shell session.

The application focuses on the common workflows needed when moving files to or from an FTP server:

- connect to FTP or FTPS endpoints with reusable profiles
- browse local and remote directories side by side
- upload and download through a transfer queue
- create directories, rename files, and delete remote or local entries
- inspect logs while working
- optionally start an embedded FTP server for testing and experimentation

The package also exposes a small CLI alongside the GUI:

- `ftplib_gui` or `ftplib_gui gui` launches the desktop app
- `ftplib_gui paths` prints the app-data, profiles, and log-file locations
- `ftplib_gui profiles` lists any saved connection profiles

See the installation and quick-start guides for setup details and everyday usage.
