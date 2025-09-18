import pytest
import tempfile
import os
from pathlib import Path
from data_loader import DataLoader


class TestDataLoader:
    
    def setup_method(self):
        self.loader = DataLoader()
    
    def test_load_valid_csv_file(self):
        content = "student_name,subject,teacher_name,date,grade\nИванов Иван,Математика,Петрова Ольга,2023-09-10,5\n"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_file = f.name
        
        try:
            data = self.loader.load_files([temp_file])
            assert len(data) == 1
            assert data[0]['student_name'] == 'Иванов Иван'
            assert data[0]['grade'] == 5.0
        finally:
            os.unlink(temp_file)
    
    def test_load_multiple_files(self):
        content1 = "student_name,subject,teacher_name,date,grade\nИванов Иван,Математика,Петрова Ольга,2023-09-10,5\n"
        content2 = "student_name,subject,teacher_name,date,grade\nПетров Петр,Физика,Сидоров Иван,2023-09-11,4\n"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f1:
            f1.write(content1)
            temp_file1 = f1.name
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f2:
            f2.write(content2)
            temp_file2 = f2.name
        
        try:
            data = self.loader.load_files([temp_file1, temp_file2])
            assert len(data) == 2
            assert data[0]['student_name'] == 'Иванов Иван'
            assert data[1]['student_name'] == 'Петров Петр'
        finally:
            os.unlink(temp_file1)
            os.unlink(temp_file2)
    
    def test_file_not_found(self):
        with pytest.raises(FileNotFoundError):
            self.loader.load_files(['nonexistent_file.csv'])
    
    def test_missing_columns(self):
        content = "name,grade\nИванов Иван,5\n"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_file = f.name
        
        try:
            with pytest.raises(ValueError, match="отсутствуют обязательные колонки"):
                self.loader.load_files([temp_file])
        finally:
            os.unlink(temp_file)
    
    def test_invalid_grade(self):
        content = "student_name,subject,teacher_name,date,grade\nИванов Иван,Математика,Петрова Ольга,2023-09-10,invalid\n"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_file = f.name
        
        try:
            with pytest.raises(ValueError, match="Некорректное значение оценки"):
                self.loader.load_files([temp_file])
        finally:
            os.unlink(temp_file)
    
    def test_grade_out_of_range(self):
        content = "student_name,subject,teacher_name,date,grade\nИванов Иван,Математика,Петрова Ольга,2023-09-10,6\n"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_file = f.name
        
        try:
            with pytest.raises(ValueError, match="Оценка должна быть от 1 до 5"):
                self.loader.load_files([temp_file])
        finally:
            os.unlink(temp_file)
    
    def test_empty_field(self):
        content = "student_name,subject,teacher_name,date,grade\n,Математика,Петрова Ольга,2023-09-10,5\n"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_file = f.name
        
        try:
            with pytest.raises(ValueError, match="Пустое значение в колонке"):
                self.loader.load_files([temp_file])
        finally:
            os.unlink(temp_file)
    
    def test_empty_file(self):
        content = "student_name,subject,teacher_name,date,grade\n"
        
        with tempfile.NamedTemporaryFile(mode='w', suffix='.csv', delete=False, encoding='utf-8') as f:
            f.write(content)
            temp_file = f.name
        
        try:
            with pytest.raises(ValueError, match="не содержит данных"):
                self.loader.load_files([temp_file])
        finally:
            os.unlink(temp_file)