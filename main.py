from HTMLParser import HTMLParser
from Queue import Queue, Empty
from threading import Thread
import requests

__author__ = 'crystal'


class RecipesListParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.ok_recipe_link = False
        self.recipe_links = []

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs = dict((name.lower(), value) for name, value in attrs)
        if tag == 'div' and attrs['class'] == 'recipe-link':
            self.ok_recipe_link = True
        if tag == 'a' and self.ok_recipe_link:
            self.recipe_links.append(attrs['href'])

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == 'div' and self.ok_recipe_link:
            self.ok_recipe_link = False


class RecipeParser(HTMLParser):
    def __init__(self):
        HTMLParser.__init__(self)
        self.ok_recipe_link = False
        self.recipe_links = []
        self.ok_preptime = False
        self.ok_servings = False
        self.ok_difficulty = False
        self.ok_directions = False
        self.ok_heading = False

    def __getattr__(self, item):
        return ''

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        attrs = dict((name.lower(), value) for name, value in attrs)
        if 'class' not in attrs.keys():
            attrs['class'] = ''

        if tag == 'h1' and 'title' in attrs['class'].split():
            self.ok_heading = True
            self.fetch_data_to_field = 'name'

        if tag == 'div' and 'group-recipe-serving-size' in attrs['class'].split():
            self.ok_servings = True
        if tag == 'span' and self.ok_servings:
            self.fetch_data_to_field = 'servings'

        if tag == 'div' and 'field-field-recipe-directions' in attrs['class'].split():
            self.ok_directions = True
        if tag == 'ol' and self.ok_directions:
            self.fetch_data_to_field = 'directions'

        if tag == 'div' and 'field-field-recipe-difficulty' in attrs['class'].split():
            self.ok_difficulty = True
        if self.ok_difficulty and tag == 'div' and 'field-item' in attrs['class'].split():
            self.fetch_data_to_field = 'difficulty'

        if tag == 'span' and 'preptime' in attrs['class'].split():
            self.ok_preptime = True
            self.fetch_data_to_field = 'preptime'
            return

        # first nested span
        if tag == 'span' and self.ok_preptime:
            self.ok_preptime = False
            self.fetch_data_to_field = None

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == 'h1' and self.ok_heading:
            self.ok_heading = False
            self.fetch_data_to_field = None

        if tag == 'span' and self.ok_servings:
            self.ok_servings = False
            self.fetch_data_to_field = None

        if tag == 'ol' and self.ok_directions:
            self.ok_directions = False
            self.fetch_data_to_field = None

        if tag == 'div' and self.ok_difficulty and self.fetch_data_to_field:
            self.ok_difficulty = False
            self.fetch_data_to_field = None


    def handle_data(self, data):
        if getattr(self, 'fetch_data_to_field', None):
            setattr(self,
                    self.fetch_data_to_field,
                    getattr(self, self.fetch_data_to_field, '') + ' ' + data.encode('utf8')
            )


def get_recipe_list():
    page_number = -1
    first_url = None
    while True:
        page_number += 1
        new_url = 'http://www.foodrepublic.com/views/ajax?page=%d&view_name=recipes&view_display_id=panel_pane_5&view_path=recipes&view_base_path=recipes'
        resp = requests.get(new_url % page_number)
        if resp.status_code != requests.codes.ok:
            raise Exception('Hell! got %s', resp.text)
        json = resp.json()
        if not json['status']:
            break

        parser = RecipesListParser()
        parser.feed(json['display'])
        if first_url == parser.recipe_links[:1]:
            break
        first_url = first_url or parser.recipe_links[:1]
        for url in parser.recipe_links:
            yield url


def parse_recipe_by_url(input_queue, output_queue):
    while True:
        recipe_url = input_queue.get()
        new_url = 'http://www.foodrepublic.com/%s' % recipe_url
        resp = requests.get(new_url)
        if resp.status_code != requests.codes.ok:
            raise Exception('Hell! got %s', resp.text)
        parser = RecipeParser()
        parser.feed(resp.text)
        input_queue.task_done()
        print('- (%d) Recipe %s processed...' % (input_queue.qsize(), recipe_url))
        output_queue.put(parser)


def main(num_worker_threads=4):
    recipe_urls = Queue()
    recipes = Queue()
    for i in range(num_worker_threads):
        t = Thread(target=parse_recipe_by_url,
                   kwargs={
                       'input_queue': recipe_urls,
                       'output_queue': recipes
                   }
        )
        t.daemon = True
        t.start()

    for recipe_url in get_recipe_list():
        recipe_urls.put(recipe_url)
        print('+ (%d) Recipe %s queued...' % (recipe_urls.qsize(), recipe_url))

    recipe_urls.join()

    while True:
        try:
            item = recipes.get_nowait()
        except Empty:
            break
        print("Name:{0.name}\n"
              "Servings:{0.servings}\n"
              "Directions:{0.directions}\n"
              "LevelofDifficulty:{0.difficulty}\n"
              "PrepTime:{0.preptime}\n".format(item))


main()
