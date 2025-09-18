import csv
from typing import List, Dict, Any
from pathlib import Path


class DataLoader:
    
    def __init__(self):
        self.required_columns = {'student_name', 'subject', 'teacher_name', 'date', 'grade'}
    
    def load_files(self, file_paths: List[str]) -> List[Dict[str, Any]]:
        all_data = []
        
        for file_path in file_paths:
            data = self._load_single_file(file_path)
            all_data.extend(data)
        
        return all_data
    
    def _load_single_file(self, file_path: str) -> List[Dict[str, Any]]:
        path = Path(file_path)
        
        if not path.exists():
            raise FileNotFoundError(f"Файл {file_path} не найден")
        
        data = []
        
        try:
            with open(path, 'r', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                
                if not self.required_columns.issubset(set(reader.fieldnames or [])):
                    missing = self.required_columns - set(reader.fieldnames or [])
                    raise ValueError(
                        f"В файле {file_path} отсутствуют обязательные колонки: {missing}"
                    )
                
                for row_num, row in enumerate(reader, start=2):
                    try:
                        processed_row = self._process_row(row, file_path, row_num)
                        data.append(processed_row)
                    except ValueError as e:
                        raise ValueError(f"Ошибка в файле {file_path}, строка {row_num}: {e}")
                        
        except UnicodeDecodeError:
            raise ValueError(f"Не удается прочитать файл {file_path}. Проверьте кодировку.")
        
        if not data:
            raise ValueError(f"Файл {file_path} не содержит данных")
        
        return data
    
    def _process_row(self, row: Dict[str, str], file_path: str, row_num: int) -> Dict[str, Any]:
        for field in self.required_columns:
            if not row.get(field, '').strip():
                raise ValueError(f"Пустое значение в колонке '{field}'")
        
        try:
            grade = float(row['grade'].strip())
            if not (1 <= grade <= 5):
                raise ValueError(f"Оценка должна быть от 1 до 5, получено: {grade}")
        except ValueError as e:
            if "could not convert" in str(e):
                raise ValueError(f"Некорректное значение оценки: '{row['grade']}'")
            raise
        
        return {
            'student_name': row['student_name'].strip(),
            'subject': row['subject'].strip(),
            'teacher_name': row['teacher_name'].strip(),
            'date': row['date'].strip(),
            'grade': grade
        }