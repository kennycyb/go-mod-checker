# go-mod-checker

A command-line tool to check the status of Go module dependencies in your `go.mod` file.

## Features

- Checks if direct Go module dependencies are:
  - **ARCHIVED** (printed in red) - Repository is archived or no longer available
  - **OUTDATED** (printed in yellow) - A newer version is available
  - **OK** (printed in green) - Up to date
- Simple and easy to use
- Installable via pip from git

## Installation

Install directly from GitHub using pip:

```bash
pip install git+https://github.com/kennycyb/go-mod-checker.git
```

## Usage

Run the command in a directory containing a `go.mod` file:

```bash
go-mod-checker
```

Or specify a path to a `go.mod` file:

```bash
go-mod-checker /path/to/go.mod
```

## Example Output

```
Checking dependencies in go.mod...

Found 5 direct dependencies:

  github.com/gin-gonic/gin v1.9.0 - OK
  github.com/stretchr/testify v1.8.0 - OUTDATED (latest: v1.8.4)
  github.com/archived/repo v1.0.0 - ARCHIVED
  golang.org/x/sync v0.1.0 - OK
  github.com/gorilla/mux v1.8.0 - OK

Summary:
  ✓ OK: 3
  ⚠ OUTDATED: 1
  ✗ ARCHIVED: 1
```

## Development

To install in development mode:

```bash
git clone https://github.com/kennycyb/go-mod-checker.git
cd go-mod-checker
pip install -e .
```

## License

MIT License - see LICENSE file for details