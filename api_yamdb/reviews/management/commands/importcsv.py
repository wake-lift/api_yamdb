import os

from django import apps
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand

import pandas

from reviews.models import Category, Comment, Genre, Review, Title


class Command(BaseCommand):
    help = """
    Команда выполняет импорт данных из csv-файлов в базу данных проекта.
    Все ранее имеющиеся данные удаляются из БД. csv-файлы должны находиться
    в каталоге "static/data/" относительно корня проекта.
    """

    CSV_DIRECTORY = os.getcwd() + "/static/data/"
    CSV_TO_MODEL_CORRESPONDENCE = {
        'category.csv': Category,
        'genre.csv': Genre,
        'titles.csv': Title,
        'genre_title.csv': apps.apps.get_model(
            app_label='reviews',
            model_name='Title_genre'
        ),
        'review.csv': Review,
        'comments.csv': Comment,
        'users.csv': get_user_model(),
    }

    def fix_titles_table(self):
        """Функция, исправляющая ошибку в названии столбца
        "category_id" в файле "titles.csv"."""
        titles_df = pandas.read_csv(self.CSV_DIRECTORY + 'titles.csv')
        titles_df.rename(columns={"category": "category_id"}, inplace=True)
        titles_df.to_csv(self.CSV_DIRECTORY + 'titles.csv', index=False)

    def handle(self, *args, **options):
        text_color_green = '\033[32m'
        text_color_red = '\033[31m'
        text_color_reset = '\033[0m'
        self.fix_titles_table()
        for csv_file, model in self.CSV_TO_MODEL_CORRESPONDENCE.items():
            dump_data = list(model.objects.values())
            try:
                df = pandas.read_csv(self.CSV_DIRECTORY + csv_file, sep=',')
                df_dict = df.to_dict('records')
                model.objects.all().delete()
                model.objects.bulk_create(model(**row) for row in df_dict)
            except Exception as error:
                model.objects.all().delete()
                if dump_data:
                    for item in dump_data:
                        model.objects.create(**item)
                print(text_color_red + 'При импорте данных из файла '
                      f'{csv_file} в таблицу {model.__name__} возникла '
                      f'ошибка: {error}.' + text_color_reset)
            else:
                print(text_color_green + f'Данные из файла {csv_file} успешно'
                      f' импортированы в таблицу {model.__name__}.'
                      + text_color_reset)
