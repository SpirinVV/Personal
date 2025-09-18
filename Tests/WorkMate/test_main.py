import pytest
import sys
from unittest.mock import patch, Mock
from main import parse_arguments, main


class TestMain:
    
    def test_parse_arguments_valid(self):
        test_args = ['main.py', '--files', 'file1.csv', 'file2.csv', '--report', 'students-performance']
        with patch('sys.argv', test_args):
            args = parse_arguments()
            assert args.files == ['file1.csv', 'file2.csv']
            assert args.report == 'students-performance'
    
    def test_parse_arguments_missing_files(self):
        test_args = ['main.py', '--report', 'students-performance']
        with patch('sys.argv', test_args):
            with pytest.raises(SystemExit):
                parse_arguments()
    
    def test_parse_arguments_missing_report(self):
        test_args = ['main.py', '--files', 'file1.csv']
        with patch('sys.argv', test_args):
            with pytest.raises(SystemExit):
                parse_arguments()
    
    def test_parse_arguments_invalid_report(self):
        test_args = ['main.py', '--files', 'file1.csv', '--report', 'invalid-report']
        with patch('sys.argv', test_args):
            with pytest.raises(SystemExit):
                parse_arguments()
    
    @patch('main.ReportFactory')
    @patch('main.DataLoader')
    @patch('main.parse_arguments')
    def test_main_success(self, mock_parse, mock_loader_class, mock_factory_class):
        mock_args = Mock()
        mock_args.files = ['test.csv']
        mock_args.report = 'students-performance'
        mock_parse.return_value = mock_args
        
        mock_loader = Mock()
        mock_loader.load_files.return_value = [{'student_name': 'Test', 'grade': 5}]
        mock_loader_class.return_value = mock_loader
        
        mock_report = Mock()
        mock_factory = Mock()
        mock_factory.create_report.return_value = mock_report
        mock_factory_class.return_value = mock_factory
        
        main()
        
        mock_loader.load_files.assert_called_once_with(['test.csv'])
        mock_factory.create_report.assert_called_once_with('students-performance')
        mock_report.generate.assert_called_once()
    
    @patch('main.DataLoader')
    @patch('main.parse_arguments')
    @patch('sys.exit')
    def test_main_file_not_found(self, mock_exit, mock_parse, mock_loader_class):
        mock_args = Mock()
        mock_args.files = ['nonexistent.csv']
        mock_args.report = 'students-performance'
        mock_parse.return_value = mock_args
        
        mock_loader = Mock()
        mock_loader.load_files.side_effect = FileNotFoundError("File not found")
        mock_loader_class.return_value = mock_loader
        
        with patch('builtins.print'):
            main()
        
        mock_exit.assert_called_once_with(1)
    
    @patch('main.DataLoader')
    @patch('main.parse_arguments')
    @patch('sys.exit')
    def test_main_value_error(self, mock_exit, mock_parse, mock_loader_class):
        mock_args = Mock()
        mock_args.files = ['test.csv']
        mock_args.report = 'students-performance'
        mock_parse.return_value = mock_args
        
        mock_loader = Mock()
        mock_loader.load_files.side_effect = ValueError("Invalid data")
        mock_loader_class.return_value = mock_loader
        
        with patch('builtins.print'):
            main()
        
        mock_exit.assert_called_once_with(1)