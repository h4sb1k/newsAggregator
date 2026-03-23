# classifier.py
import re
from typing import Optional, Dict, List

# Новая структура классификации с приоритетами
REGION_KEYWORDS = {
    "Россия": {
        "countries": [
            "россия", "russia", "rf", "рф", "russian federation",
            "российская федерация"
        ],
        "cities": [
            "москва", "moscow", "санкт-петербург", "saint petersburg",
            "ленинград", "leningrad", "новосибирск", "екатеринбург",
            "казань", "нижний новгород"
        ],
        "politics": [
            "кремль", "kremlin", "путин", "putin", "медведев", "medvedev",
            "мишустин", "lavrov", "лавров", "госдума", "duma", "совет федерации"
        ],
        "context": [
            "рубль", "ruble", "rub", "мосбиржа", "moex", "российский",
            "russian", "в россии", "in russia"
        ]
    },

    "США": {
        "countries": [
            "сша", "usa", "us", "united states", "america", "америка",
            "united states of america", "соединенные штаты"
        ],
        "institutions": [
            "white house", "белый дом", "congress", "конгресс", "senate",
            "сенат", "pentagon", "пентагон", "state department",
            "федеральная резервная система", "federal reserve", "fed", "фрс",
            "sec", "sec usa", "fbi", "cia", "nsa"
        ],
        "politics": [
            "president of the united states", "президент сша",
            "biden", "байден", "trump", "трамп", "vance", "ванс",
            "republican", "республиканец", "democrat", "демократ",
            "election us", "выборы сша"
        ],
        "locations": [
            "washington dc", "вашингтон", "new york", "нью-йорк",
            "california", "калифорния", "texas", "техас", "florida",
            "флорида", "wall street", "уолл-стрит", "silicon valley",
            "кремниевая долина"
        ],
        "context": [
            "us dollar", "доллар", "usd", "nasdaq", "dow jones",
            "s&p 500", "american", "американский", "us economy"
        ]
    },

    "Украина": {
        "countries": [
            "украина", "ukraine", "ua"
        ],
        "cities": [
            "киев", "kyiv", "kiev", "харьков", "kharkiv", "львов",
            "lviv", "одесса", "odesa", "днепр", "dnipro"
        ],
        "politics": [
            "зеленский", "zelensky", "зеленский", "poroshenko", "порошенко",
            "рада", "verkhovna rada", "кабинет министров украины"
        ],
        "context": [
            "гривна", "hryvnia", "uah", "украинский", "ukrainian",
            "в украине", "in ukraine", "киевский"
        ]
    },

    "Европа": {
        "countries": [
            "германия", "germany", "франция", "france", "великобритания",
            "united kingdom", "uk", "britain", "британия", "италия", "italy",
            "испания", "spain", "польша", "poland", "беларусь", "belarus",
            "нидерланды", "netherlands", "швеция", "sweden", "норвегия",
            "norway", "финляндия", "finland", "чехия", "czechia", "czech",
            "венгрия", "hungary", "румыния", "romania", "болгария", "bulgaria",
            "греция", "greece", "турция", "turkey", "türkiye", "португалия",
            "portugal", "австрия", "austria", "швейцария", "switzerland"
        ],
        "cities": [
            "берлин", "berlin", "париж", "paris", "лондон", "london",
            "рим", "rome", "мадрид", "madrid", "варшава", "warsaw",
            "минск", "minsk", "амстердам", "amsterdam", "стокгольм",
            "stockholm", "осло", "oslo", "хельсинки", "helsinki",
            "прага", "prague", "будапешт", "budapest", "бухарест", "bucharest",
            "софия", "sofia", "атены", "athens", "анкара", "ankara"
        ],
        "organizations": [
            "european union", "европейский союз", "eu", "es", "eurozone",
            "еврозона", "nato", "нато", "schengen", "шенген", "ecb",
            "ецб", "council of europe"
        ],
        "context": [
            "евро", "euro", "eur", "европейский", "european", "brexit",
            "в европе", "in europe"
        ]
    },

    "Северная Америка": {
        "countries": [
            "канада", "canada", "мексика", "mexico"
        ],
        "cities": [
            "оттава", "ottawa", "торонто", "toronto", "монреаль", "montreal",
            "ванкувер", "vancouver", "мехико", "mexico city", "гвадалахара"
        ],
        "context": [
            "канадский", "canadian", "cad", "мексиканский", "mexican",
            "mxn", "в канаде", "in canada", "в мексике", "in mexico"
        ]
    },

    "Латинская Америка": {
        "countries": [
            "бразилия", "brazil", "аргентина", "argentina", "чили", "chile",
            "колумбия", "colombia", "перу", "peru", "венесуэла", "venezuela",
            "куба", "cuba", "боливия", "bolivia", "эквадор", "ecuador",
            "парагвай", "paraguay", "уругвай", "uruguay"
        ],
        "cities": [
            "бразилиа", "brasilia", "сан-паулу", "sao paulo", "буэнос-айрес",
            "buenos aires", "сантьяго", "santiago", "богота", "bogota",
            "лима", "lima", "каракас", "caracas", "гавана", "havana"
        ],
        "context": [
            "латинская америка", "latin america", "latam", "бразильский",
            "brazilian", "аргентинский", "argentine"
        ]
    },

    "Ближний Восток": {
        "countries": [
            "израиль", "israel", "иран", "iran", "саудовская аравия",
            "saudi arabia", "оаэ", "uae", "объединенные арабские эмираты",
            "united arab emirates", "катар", "qatar", "ирак", "iraq",
            "сирия", "syria", "ливан", "lebanon", "иордания", "jordan",
            "йемен", "yemen", "палестина", "palestine", "египет", "egypt"
        ],
        "cities": [
            "тель-авив", "tel aviv", "иерусалим", "jerusalem", "тегеран",
            "tehran", "эр-рияд", "riyadh", "дубай", "dubai", "доха", "doha",
            "багдад", "baghdad", "дамаск", "damascus", "бейрут", "beirut",
            "амман", "amman", "каир", "cairo"
        ],
        "organizations": [
            "gcc", "оаэ", "opec", "опек", "arab league", "лига арабских государств",
            "hamas", "хамас", "hezbollah", "хезболла", "houthis", "хуситы"
        ],
        "context": [
            "ближний восток", "middle east", "нефть", "oil", "баррель",
            "баррель нефти", "israel-hamas", "иран-израиль"
        ]
    },

    "Азия": {
        "countries": [
            "китай", "china", "индия", "india", "япония", "japan",
            "южная корея", "south korea", "корея", "korea", "вьетнам",
            "vietnam", "таиланд", "thailand", "индонезия", "indonesia",
            "филиппины", "philippines", "малайзия", "malaysia", "сингапур",
            "singapore", "пакистан", "pakistan", "казахстан", "kazakhstan",
            "узбекистан", "uzbekistan", "монголия", "mongolia"
        ],
        "cities": [
            "пекин", "beijing", "шанхай", "shanghai", "нью-дели", "new delhi",
            "токио", "tokyo", "сеул", "seoul", "ханой", "hanoi", "бангкок",
            "bangkok", "джакарта", "jakarta", "манила", "manila", "алматы",
            "астана", "astana", "улан-батор", "ulaanbaatar"
        ],
        "context": [
            "азиатский", "asian", "юань", "yuan", "cny", "йена", "yen",
            "jpy", "рупия", "rupee", "вона", "won", "asean", "асеан",
            "в азии", "in asia"
        ]
    },

    "Африка": {
        "countries": [
            "юар", "south africa", "нигерия", "nigeria", "египет", "egypt",
            "марокко", "morocco", "алжир", "algeria", "тунис", "tunisia",
            "эфиопия", "ethiopia", "кения", "kenya", "гана", "ghana"
        ],
        "cities": [
            "йоханнесбург", "johannesburg", "кейптаун", "cape town",
            "лагос", "lagos", "каир", "cairo", "рабат", "rabat", "алжир",
            "algiers", "аддис-абеба", "addis ababa", "найроби", "nairobi",
            "аккра", "accra"
        ],
        "context": [
            "африка", "africa", "африканский", "african", "в африке",
            "in africa"
        ]
    },

    "Австралия и Океания": {
        "countries": [
            "австралия", "australia", "новая зеландия", "new zealand"
        ],
        "cities": [
            "канберра", "canberra", "сидней", "sydney", "мельбурн", "melbourne",
            "веллингтон", "wellington", "окленд", "auckland"
        ],
        "context": [
            "австралийский", "australian", "aud", "океания", "oceania",
            "в австралии", "in australia"
        ]
    }
}


def classify_news_region(title: str, description: str = "") -> str:
    """
    Классифицирует новость по региону на основе ключевых слов.

    Приоритеты классификации:
    1. Россия
    2. США
    3. Украина
    4. Остальные регионы

    Args:
        title: Заголовок новости
        description: Описание новости (опционально)

    Returns:
        Название региона (например, 'Россия', 'США', 'Европа')
        или 'International' если не удалось классифицировать
    """
    text = f"{title} {description}".lower()

    scores: Dict[str, int] = {}

    for region, keyword_dict in REGION_KEYWORDS.items():
        score = 0
        for keyword_list in keyword_dict.values():
            for keyword in keyword_list:
                # Используем поиск по слову, чтобы избежать частичных совпадений
                if re.search(rf'\b{re.escape(keyword)}\b', text, re.IGNORECASE):
                    score += 1
        if score > 0:
            scores[region] = score

    if scores:
        max_score = max(scores.values())
        candidates = [r for r, s in scores.items() if s == max_score]

        # Приоритет при равенстве очков или пересечении ключевых слов
        # Порядок строго соответствует заданию: Россия > США > Украина > Остальные
        priority = [
            "Россия",
            "США",
            "Украина",
            "Европа",
            "Ближний Восток",
            "Азия",
            "Северная Америка",
            "Латинская Америка",
            "Африка",
            "Австралия и Океания"
        ]

        for region in priority:
            if region in candidates:
                return region

    return "International"


def classify_articles(articles: List[dict]) -> List[dict]:
    """
    Классифицирует массив статей по регионам.

    Args:
        articles: Список словарей с новостями (ключи 'title', 'description')

    Returns:
        Список словарей с добавленным полем 'category'
    """
    for article in articles:
        article['category'] = classify_news_region(
            article.get('title', ''),
            article.get('description', '')
        )
    return articles