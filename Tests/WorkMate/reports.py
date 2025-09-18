from abc import ABC, abstractmethod
from typing import List, Dict, Any, Type
from collections import defaultdict
from tabulate import tabulate


class BaseReport(ABC):
    
    @abstractmethod
    def generate(self, data: List[Dict[str, Any]]) -> None:
        pass


class StudentsPerformanceReport(BaseReport):
    
    def generate(self, data: List[Dict[str, Any]]) -> None:
        if not data:
            print("Нет данных для формирования отчета")
            return
        
        student_grades = defaultdict(list)
        
        for record in data:
            student_name = record['student_name']
            grade = record['grade']
            student_grades[student_name].append(grade)
        
        student_averages = []
        for student_name, grades in student_grades.items():
            average_grade = sum(grades) / len(grades)
            student_averages.append({
                'student_name': student_name,
                'grade': round(average_grade, 1)
            })
        
        student_averages.sort(key=lambda x: x['grade'], reverse=True)
        
        table_data = [
            [i + 1, student['student_name'], student['grade']]
            for i, student in enumerate(student_averages)
        ]
        
        headers = ['№', 'student_name', 'grade']
        print(tabulate(table_data, headers=headers, tablefmt='grid'))


class ReportFactory:
    
    def __init__(self):
        self._reports: Dict[str, Type[BaseReport]] = {
            'students-performance': StudentsPerformanceReport
        }
    
    def create_report(self, report_type: str) -> BaseReport:
        if report_type not in self._reports:
            supported_types = ', '.join(self._reports.keys())
            raise ValueError(
                f"Неподдерживаемый тип отчета: '{report_type}'. "
                f"Поддерживаемые типы: {supported_types}"
            )
        
        report_class = self._reports[report_type]
        return report_class()
    
    def register_report(self, report_type: str, report_class: Type[BaseReport]) -> None:
        if not issubclass(report_class, BaseReport):
            raise ValueError("Класс отчета должен наследоваться от BaseReport")
        
        self._reports[report_type] = report_class
    
    def get_available_reports(self) -> List[str]:
        return list(self._reports.keys())