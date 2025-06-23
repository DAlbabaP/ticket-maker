from flask import Flask, render_template, request, send_file, jsonify
from datetime import datetime, date
import io
from reportlab.pdfgen import canvas
from reportlab.lib.pagesizes import A4
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
import os
import tempfile

app = Flask(__name__)
app.secret_key = 'ticket-generator-secret-key'

# Регистрируем шрифт с поддержкой кириллицы при запуске приложения
def register_fonts():
    try:
        # Пытаемся использовать системные шрифты Windows (для локальной разработки)
        import platform
        if platform.system() == 'Windows':
            # Путь к системным шрифтам Windows
            font_path = 'C:/Windows/Fonts/'
            # Регистрируем Arial Unicode MS или другие системные шрифты
            try:
                pdfmetrics.registerFont(TTFont('ArialUnicode', font_path + 'arial.ttf'))
                return 'ArialUnicode'
            except:
                pass
            
            try:
                pdfmetrics.registerFont(TTFont('TimesUnicode', font_path + 'times.ttf'))
                return 'TimesUnicode'
            except:
                pass
        
        # Fallback для хостинга - используем встроенные шрифты ReportLab с кириллицей
        try:
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont
            pdfmetrics.registerFont(UnicodeCIDFont('HeiseiMin-W3'))
            return 'HeiseiMin-W3'
        except:
            pass
            
        try:
            from reportlab.pdfbase.cidfonts import UnicodeCIDFont  
            pdfmetrics.registerFont(UnicodeCIDFont('HeiseiKakuGo-W5'))
            return 'HeiseiKakuGo-W5'
        except:
            pass
        
        # Последний fallback - стандартные шрифты
        return None
    except:
        return None

# Регистрируем шрифт при загрузке модуля
UNICODE_FONT = register_fonts()
print(f"Используемый шрифт: {UNICODE_FONT if UNICODE_FONT else 'Стандартный Helvetica с транслитерацией'}")

class TicketGenerator:
    @staticmethod
    def parse_data(text):
        """Парсинг данных из текста"""
        if not text.strip():
            raise ValueError("Данные не введены!")
        
        lines = text.split('\n')
        current_role = None
        people_by_role = {}
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
            
            if line.startswith('[') and line.endswith(']'):
                current_role = line[1:-1].strip().upper()
                if current_role not in people_by_role:
                    people_by_role[current_role] = []
            elif current_role:
                people_by_role[current_role].append(line)
        
        if not people_by_role:
            raise ValueError("Не найдено ни одной роли или человека!")
        
        return people_by_role
    
    @staticmethod
    def generate_tickets(people_by_role, selected_date, role_settings):
        """Генерация талонов"""
        tickets = []
        
        for role, people in people_by_role.items():
            # Получаем настройки для этой роли
            settings = role_settings.get(role, {
                'lunch': True,
                'dinner': True,
                'meal_type': 'Салат + Горячее'
            })
            
            has_lunch = settings.get('lunch', True)
            has_dinner = settings.get('dinner', True)
            meal_type = settings.get('meal_type', 'Салат + Горячее')
            
            for person in people:
                if has_lunch:
                    tickets.append({
                        'name': person,
                        'role': role,
                        'meal_time': 'ОБЕД',
                        'meal_type': meal_type,
                        'date': selected_date
                    })
                
                if has_dinner:
                    tickets.append({
                        'name': person,
                        'role': role,
                        'meal_time': 'УЖИН',
                        'meal_type': meal_type,
                        'date': selected_date
                    })
        
        return tickets
    @staticmethod
    def create_pdf(tickets):
        """Создание PDF с талонами"""
        buffer = io.BytesIO()
        c = canvas.Canvas(buffer, pagesize=A4)
        width, height = A4
        
        # Размеры талона (очень компактные)
        ticket_width = 35 * mm  # Уменьшено с 90 до 35 мм
        ticket_height = 20 * mm  # Уменьшено с 45 до 20 мм
        
        # Количество талонов на странице
        tickets_per_row = 5  # Увеличено с 2 до 5
        tickets_per_col = 14  # Увеличено с 6 до 14
        tickets_per_page = tickets_per_row * tickets_per_col  # = 70 талонов на страницу
        
        # Отступы (минимальные)
        margin_x = (width - tickets_per_row * ticket_width) / 2
        margin_y = (height - tickets_per_col * ticket_height) / 2
        
        for i, ticket in enumerate(tickets):
            if i > 0 and i % tickets_per_page == 0:
                c.showPage()  # Новая страница
            
            # Позиция талона на странице
            page_index = i % tickets_per_page
            row = page_index // tickets_per_row
            col = page_index % tickets_per_row
            x = margin_x + col * ticket_width
            y = height - margin_y - (row + 1) * ticket_height
            
            TicketGenerator.draw_ticket(c, x, y, ticket_width, ticket_height, ticket)
        
        c.save()
        buffer.seek(0)
        return buffer
    
    @staticmethod
    def draw_ticket(c, x, y, width, height, ticket):
        """Рисование одного компактного талона"""
        # Рамка
        c.setLineWidth(0.5)  # Тонкая рамка
        c.rect(x, y, width, height)
        
        # Минимальные отступы
        padding = 1 * mm
          # Функция для безопасного вывода текста
        def safe_draw_string(canvas, x_pos, y_pos, text, font_name, font_size):
            try:
                if UNICODE_FONT:
                    canvas.setFont(UNICODE_FONT, font_size)
                    canvas.drawString(x_pos, y_pos, text)
                    return
            except Exception as e:
                pass
            
            # Пробуем стандартные шрифты с транслитерацией
            try:
                canvas.setFont('Helvetica', font_size)
                transliterated = TicketGenerator.transliterate(text)
                canvas.drawString(x_pos, y_pos, transliterated)
                return
            except Exception as e:
                pass
            
            # Последний шанс - только ASCII символы
            try:
                canvas.setFont('Helvetica', font_size)
                ascii_text = ''.join(char if ord(char) < 128 else '?' for char in text)
                canvas.drawString(x_pos, y_pos, ascii_text)
            except Exception as e:
                # Если совсем ничего не работает - пропускаем
                pass
          # Заголовок - полный тип питания и дата
        header_text = f"{ticket['meal_time']} {ticket['date']}"
        safe_draw_string(c, x + padding, y + height - 4 * mm, header_text, 'Helvetica-Bold', 6)
        
        # Имя - сокращенное для экономии места
        name = ticket['name']
        # Сокращаем ФИО до фамилии и инициалов
        words = name.split()
        if len(words) >= 3:
            short_name = f"{words[0]} {words[1][0]}.{words[2][0]}."
        elif len(words) >= 2:
            short_name = f"{words[0]} {words[1][0]}."
        else:
            short_name = words[0] if words else name
            
        safe_draw_string(c, x + padding, y + height - 8 * mm, short_name, 'Helvetica-Bold', 5)
        
        # Меню - полное название
        safe_draw_string(c, x + padding, y + height - 12 * mm, ticket['meal_type'], 'Helvetica', 5)
          # Роль - полное название
        safe_draw_string(c, x + padding, y + height - 16 * mm, ticket['role'], 'Helvetica', 4)
    
    @staticmethod
    def transliterate(text):
        """Транслитерация русского текста в латиницу (fallback)"""
        translit_dict = {
            'а': 'a', 'б': 'b', 'в': 'v', 'г': 'g', 'д': 'd', 'е': 'e', 'ё': 'e',
            'ж': 'zh', 'з': 'z', 'и': 'i', 'й': 'j', 'к': 'k', 'л': 'l', 'м': 'm',
            'н': 'n', 'о': 'o', 'п': 'p', 'р': 'r', 'с': 's', 'т': 't', 'у': 'u',
            'ф': 'f', 'х': 'h', 'ц': 'c', 'ч': 'ch', 'ш': 'sh', 'щ': 'sch',
            'ъ': '', 'ы': 'y', 'ь': '', 'э': 'e', 'ю': 'ju', 'я': 'ja',
            'А': 'A', 'Б': 'B', 'В': 'V', 'Г': 'G', 'Д': 'D', 'Е': 'E', 'Ё': 'E',
            'Ж': 'ZH', 'З': 'Z', 'И': 'I', 'Й': 'J', 'К': 'K', 'Л': 'L', 'М': 'M',
            'Н': 'N', 'О': 'O', 'П': 'P', 'Р': 'R', 'С': 'S', 'Т': 'T', 'У': 'U',
            'Ф': 'F', 'Х': 'H', 'Ц': 'C', 'Ч': 'CH', 'Ш': 'SH', 'Щ': 'SCH',
            'Ъ': '', 'Ы': 'Y', 'Ь': '', 'Э': 'E', 'Ю': 'JU', 'Я': 'JA',
            # Дополнительные символы
            '№': 'No', '—': '-', '–': '-', '"': '"', '"': '"', '«': '"', '»': '"'
        }
        
        result = ''
        for char in text:
            result += translit_dict.get(char, char)
        return result

@app.route('/')
def index():
    """Главная страница"""
    today = date.today().strftime("%Y-%m-%d")
    return render_template('index.html', today=today)

@app.route('/get-roles', methods=['POST'])
def get_roles():
    """Получение ролей из текста"""
    try:
        data = request.json
        text_data = data.get('text_data', '')
        
        if not text_data.strip():
            return jsonify({'roles': []})
        
        people_by_role = TicketGenerator.parse_data(text_data)
        roles = list(people_by_role.keys())
        
        return jsonify({'roles': roles})
        
    except Exception as e:
        return jsonify({'roles': [], 'error': str(e)})

@app.route('/generate', methods=['POST'])
def generate():
    """Генерация талонов"""
    try:
        data = request.json
        
        # Получаем данные
        text_data = data.get('text_data', '')
        selected_date = data.get('date', '')
        role_settings = data.get('role_settings', {})
        
        # Проверяем дату
        try:
            datetime.strptime(selected_date, "%Y-%m-%d")
            # Конвертируем в нужный формат
            date_obj = datetime.strptime(selected_date, "%Y-%m-%d")
            formatted_date = date_obj.strftime("%d.%m.%Y")
        except ValueError:
            return jsonify({'error': 'Неверный формат даты!'}), 400
        
        # Парсим данные
        people_by_role = TicketGenerator.parse_data(text_data)
        
        # Генерируем талоны
        tickets = TicketGenerator.generate_tickets(people_by_role, formatted_date, role_settings)
        
        if not tickets:
            return jsonify({'error': 'Не создано ни одного талона!'}), 400
        
        # Создаем PDF
        pdf_buffer = TicketGenerator.create_pdf(tickets)
        
        # Сохраняем во временный файл
        temp_file = tempfile.NamedTemporaryFile(delete=False, suffix='.pdf')
        temp_file.write(pdf_buffer.getvalue())
        temp_file.close()
        
        return jsonify({
            'success': True,
            'tickets_count': len(tickets),
            'download_url': f'/download/{os.path.basename(temp_file.name)}'
        })
        
    except Exception as e:
        return jsonify({'error': str(e)}), 400

@app.route('/download/<filename>')
def download(filename):
    """Скачивание PDF файла"""
    temp_path = os.path.join(tempfile.gettempdir(), filename)
    if os.path.exists(temp_path):
        return send_file(temp_path, as_attachment=True, download_name=f'talony_{date.today().strftime("%d_%m_%Y")}.pdf')
    else:
        return "Файл не найден", 404

if __name__ == '__main__':
    import os
    port = int(os.environ.get('PORT', 5000))
    debug = os.environ.get('FLASK_ENV') == 'development'
    app.run(debug=debug, host='0.0.0.0', port=port)
