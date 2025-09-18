import pytest
from unittest.mock import patch
from io import StringIO
from reports import StudentsPerformanceReport, ReportFactory, BaseReport


class TestStudentsPerformanceReport:
    
    def setup_method(self):
        self.report = StudentsPerformanceReport()
    
    def test_generate_report_with_data(self):
        data = [
            {'student_name': 'Иванов Иван', 'grade': 5.0},
            {'student_name': 'Петров Петр', 'grade': 4.0},
            {'student_name': 'Иванов Иван', 'grade': 4.0},
            {'student_name': 'Сидоров Сидор', 'grade': 3.0},
        ]
        
        with patch('builtins.print') as mock_print:
            self.report.generate(data)
            mock_print.assert_called()
            
    def test_generate_report_empty_data(self):
        data = []
        
        with patch('builtins.print') as mock_print:
            self.report.generate(data)
            mock_print.assert_called_with("Нет данных для формирования отчета")
    
    def test_calculate_averages_correctly(self):
        data = [
            {'student_name': 'Иванов Иван', 'grade': 5.0},
            {'student_name': 'Иванов Иван', 'grade': 3.0},
            {'student_name': 'Петров Петр', 'grade': 4.0},
        ]
        
        with patch('builtins.print'):
            self.report.generate(data)


class TestReportFactory:
    
    def setup_method(self):
        self.factory = ReportFactory()
    
    def test_create_valid_report(self):
        report = self.factory.create_report('students-performance')
        assert isinstance(report, StudentsPerformanceReport)
    
    def test_create_invalid_report(self):
        with pytest.raises(ValueError, match="Неподдерживаемый тип отчета"):
            self.factory.create_report('invalid-report')
    
    def test_register_new_report(self):
        class TestReport(BaseReport):
            def generate(self, data):
                pass
        
        self.factory.register_report('test-report', TestReport)
        report = self.factory.create_report('test-report')
        assert isinstance(report, TestReport)
    
    def test_register_invalid_report_class(self):
        class InvalidReport:
            pass
        
        with pytest.raises(ValueError, match="должен наследоваться от BaseReport"):
            self.factory.register_report('invalid', InvalidReport)
    
    def test_get_available_reports(self):
        reports = self.factory.get_available_reports()
        assert 'students-performance' in reports
        assert isinstance(reports, list)