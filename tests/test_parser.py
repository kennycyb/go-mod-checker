"""Tests for go-mod-checker."""

import pytest
import tempfile
import os
from pathlib import Path

from go_mod_checker.checker import GoModParser


def test_parser_with_simple_require():
    """Test parsing a go.mod with simple require statements."""
    content = """module example.com/test

go 1.21

require (
    github.com/gin-gonic/gin v1.9.0
    github.com/stretchr/testify v1.8.0
)
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mod', delete=False) as f:
        f.write(content)
        f.flush()
        filepath = f.name
    
    try:
        parser = GoModParser(filepath)
        modules = parser.parse()
        
        assert len(modules) == 2
        assert modules[0].name == 'github.com/gin-gonic/gin'
        assert modules[0].version == 'v1.9.0'
        assert not modules[0].is_indirect
        assert modules[1].name == 'github.com/stretchr/testify'
        assert modules[1].version == 'v1.8.0'
    finally:
        os.unlink(filepath)


def test_parser_excludes_indirect_dependencies():
    """Test that indirect dependencies are excluded."""
    content = """module example.com/test

go 1.21

require (
    github.com/gin-gonic/gin v1.9.0
    github.com/indirect/dep v1.0.0 // indirect
)
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mod', delete=False) as f:
        f.write(content)
        f.flush()
        filepath = f.name
    
    try:
        parser = GoModParser(filepath)
        modules = parser.parse()
        
        assert len(modules) == 1
        assert modules[0].name == 'github.com/gin-gonic/gin'
    finally:
        os.unlink(filepath)


def test_parser_with_single_line_require():
    """Test parsing single line require statements."""
    content = """module example.com/test

go 1.21

require github.com/gorilla/mux v1.8.0
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mod', delete=False) as f:
        f.write(content)
        f.flush()
        filepath = f.name
    
    try:
        parser = GoModParser(filepath)
        modules = parser.parse()
        
        assert len(modules) == 1
        assert modules[0].name == 'github.com/gorilla/mux'
        assert modules[0].version == 'v1.8.0'
    finally:
        os.unlink(filepath)


def test_parser_file_not_found():
    """Test that FileNotFoundError is raised for missing file."""
    parser = GoModParser('/nonexistent/path/go.mod')
    
    with pytest.raises(FileNotFoundError):
        parser.parse()


def test_parser_empty_require_block():
    """Test parsing a go.mod with no dependencies."""
    content = """module example.com/test

go 1.21
"""
    with tempfile.NamedTemporaryFile(mode='w', suffix='.mod', delete=False) as f:
        f.write(content)
        f.flush()
        filepath = f.name
    
    try:
        parser = GoModParser(filepath)
        modules = parser.parse()
        
        assert len(modules) == 0
    finally:
        os.unlink(filepath)
