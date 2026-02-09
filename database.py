"""
Модуль для работы с базой данных SQLite
"""

import sqlite3
from datetime import datetime
from typing import List, Tuple, Optional


class Database:
    def __init__(self, db_file='expenses.db'):
        """Инициализация БД"""
        self.db_file = db_file
        self.init_db()
    
    def init_db(self):
        """Создание таблиц если их нет"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS expenses (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                username TEXT NOT NULL,
                amount REAL NOT NULL,
                category TEXT NOT NULL,
                description TEXT NOT NULL,
                date TEXT NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
    
    def add_expense(self, user_id: int, username: str, amount: float, 
                   category: str, description: str) -> int:
        """Добавить расход"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        date = datetime.now().isoformat()
        
        cursor.execute('''
            INSERT INTO expenses (user_id, username, amount, category, description, date)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (user_id, username, amount, category, description, date))
        
        expense_id = cursor.lastrowid
        conn.commit()
        conn.close()
        
        return expense_id
    
    def delete_expense(self, expense_id: int) -> bool:
        """Удалить расход"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('DELETE FROM expenses WHERE id = ?', (expense_id,))
        
        deleted = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return deleted
    
    def update_expense(self, expense_id: int, amount: float = None, 
                      category: str = None, description: str = None) -> bool:
        """Обновить расход"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        updates = []
        params = []
        
        if amount is not None:
            updates.append('amount = ?')
            params.append(amount)
        if category is not None:
            updates.append('category = ?')
            params.append(category)
        if description is not None:
            updates.append('description = ?')
            params.append(description)
        
        if not updates:
            return False
        
        params.append(expense_id)
        query = f"UPDATE expenses SET {', '.join(updates)} WHERE id = ?"
        
        cursor.execute(query, params)
        
        updated = cursor.rowcount > 0
        conn.commit()
        conn.close()
        
        return updated
    
    def get_recent_expenses(self, limit: int = 10) -> List[Tuple]:
        """Получить последние расходы"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, user_id, username, amount, category, description, date
            FROM expenses
            ORDER BY date DESC
            LIMIT ?
        ''', (limit,))
        
        expenses = cursor.fetchall()
        conn.close()
        
        return expenses
    
    def get_total(self, start_date: datetime = None) -> float:
        """Получить общую сумму расходов"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        if start_date:
            cursor.execute('''
                SELECT SUM(amount) FROM expenses
                WHERE date >= ?
            ''', (start_date.isoformat(),))
        else:
            cursor.execute('SELECT SUM(amount) FROM expenses')
        
        result = cursor.fetchone()[0]
        conn.close()
        
        return result or 0.0
    
    def get_by_category(self, start_date: datetime = None) -> List[Tuple[str, float]]:
        """Получить сумму по категориям"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        if start_date:
            cursor.execute('''
                SELECT category, SUM(amount)
                FROM expenses
                WHERE date >= ?
                GROUP BY category
                ORDER BY SUM(amount) DESC
            ''', (start_date.isoformat(),))
        else:
            cursor.execute('''
                SELECT category, SUM(amount)
                FROM expenses
                GROUP BY category
                ORDER BY SUM(amount) DESC
            ''')
        
        result = cursor.fetchall()
        conn.close()
        
        return result
    
    def get_by_user(self, start_date: datetime = None) -> List[Tuple[str, float]]:
        """Получить сумму по пользователям"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        if start_date:
            cursor.execute('''
                SELECT username, SUM(amount)
                FROM expenses
                WHERE date >= ?
                GROUP BY username
                ORDER BY SUM(amount) DESC
            ''', (start_date.isoformat(),))
        else:
            cursor.execute('''
                SELECT username, SUM(amount)
                FROM expenses
                GROUP BY username
                ORDER BY SUM(amount) DESC
            ''')
        
        result = cursor.fetchall()
        conn.close()
        
        return result
    
    def get_by_user_and_category(self, start_date: datetime = None) -> List[Tuple[str, str, float]]:
        """Получить сумму по пользователям и категориям"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        if start_date:
            cursor.execute('''
                SELECT username, category, SUM(amount)
                FROM expenses
                WHERE date >= ?
                GROUP BY username, category
                ORDER BY username, category
            ''', (start_date.isoformat(),))
        else:
            cursor.execute('''
                SELECT username, category, SUM(amount)
                FROM expenses
                GROUP BY username, category
                ORDER BY username, category
            ''')
        
        result = cursor.fetchall()
        conn.close()
        
        return result
    
    def get_expense_by_id(self, expense_id: int) -> Optional[Tuple]:
        """Получить расход по ID"""
        conn = sqlite3.connect(self.db_file)
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT id, user_id, username, amount, category, description, date
            FROM expenses
            WHERE id = ?
        ''', (expense_id,))
        
        expense = cursor.fetchone()
        conn.close()
        
        return expense
