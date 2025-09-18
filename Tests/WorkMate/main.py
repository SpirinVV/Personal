#!/usr/bin/env python3

import argparse
import sys
from typing import List

from data_loader import DataLoader
from reports import ReportFactory


def parse_arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Анализ успеваемости студентов из CSV файлов"
    )
    
    parser.add_argument(
        "--files",
        nargs="+",
        required=True,
        help="Пути к CSV файлам с данными студентов"
    )
    
    parser.add_argument(
        "--report",
        required=True,
        choices=["students-performance"],
        help="Тип отчета для формирования"
    )
    
    return parser.parse_args()


def main():
    try:
        args = parse_arguments()
        
        loader = DataLoader()
        data = loader.load_files(args.files)
        
        report_factory = ReportFactory()
        report = report_factory.create_report(args.report)
        report.generate(data)
        
    except FileNotFoundError as e:
        print(f"Ошибка: Файл не найден - {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Ошибка: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Неожиданная ошибка: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()