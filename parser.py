import os
import time
from abc import ABCMeta, abstractmethod
from dataclasses import dataclass, asdict

import pandas as pd
from bs4 import BeautifulSoup
from selenium import webdriver

from saver import save_to_csv


GECKODRIVER_PATH = 'geckodriver'


months = {
    'Jan': '01',
    'Feb': '02',
    'Mar': '03',
    'Apr': '04',
    'May': '05',
    'Jun': '06',
    'Jul': '07',
    'Aug': '08',
    'Sep': '09',
    'Oct': '10',
    'Nov': '11',
    'Dec': '12',
}


class LinksParser(metaclass=ABCMeta):

    def __init__(self, browser):
        self._browser = browser

    @abstractmethod
    def get_url(self, *args):
        """Возвращает ссылку на страницу с необходимыми данными."""

    @abstractmethod
    def get_links(self, filename):
        """Получает необходимые ссылки."""


class TodayLinksParser(LinksParser):

    def get_url(self):
        return 'https://www.oddsportal.com/matches/soccer/'

    def get_links(self, filename):
        links = []
        url = self.get_url()
        self._browser.get(url)
        time.sleep(0.1)
        soup = BeautifulSoup(self._browser.page_source, 'html.parser')

        data = str(soup).split('name table-participant')

        for elem in data[1:]:
            if 'soccer/' in elem:
                link = 'https://www.oddsportal.com/' + elem.split('href=\"/')[1].split('\">')[0]
                links.append(link)

        with open(filename, 'w') as f:
            f.write('\n'.join(list(set(links))))


class ByLeagueLinksParser(LinksParser):

    def __init__(self, browser, url):
        super().__init__(browser)
        self._url = url

    def get_url(self, num_page):
        return f'{self._url}/#/page/{num_page}'

    def get_links(self, filename):
        index = 1
        links = []
        while True:
            url = self.get_url(index)
            self._browser.get(url)
            time.sleep(0.1)
            index += 1
            soup = BeautifulSoup(self._browser.page_source, 'html.parser')

            soup = str(soup)
            if 'No data available' in soup:
                break
            data = soup.split('name table-participant')

            for elem in data[1:]:
                if 'soccer/' in elem:
                    link = 'https://www.oddsportal.com/' + elem.split('href=\"/')[1].split('\">')[0]
                    links.append(link)

        with open(filename, 'w') as f:
            f.write('\n'.join(list(set(links))))


@dataclass
class MatchInfo:
    date: str
    season: int
    country: str
    league: str
    team1: str
    team2: str
    home: float
    draw: float
    away: float
    over: float
    under: float
    yes: float
    no: float
    link: str


@dataclass
class HistoricalMatchInfo(MatchInfo):
    result: int
    amount: int
    both: int


@dataclass
class ResultMatchInfo:
    result: int
    amount: int
    both: int
    link: str


class Parser:

    def __init__(self, browser, url):
        self._browser = browser
        self._results_url = f'{url}#1X2;2'
        self._amounts_url = f'{url}#over-under;2'
        self._both_url = f'{url}#bts;2'
        self._results_page = None
        self._amounts_page = None
        self._both_page = None

    def get_match_info(self):
        self._get_pages()
        date = self._extract_date()
        season = self._extract_season(date)
        country, league = self._extract_country_league()
        team1, team2 = self._extract_teams()
        home, draw, away = self._extract_home_draw_away()
        over, under = self._extract_over_under()
        yes, no = self._extract_both()
        return asdict(MatchInfo(
            date=date,
            season=season,
            country=country,
            league=league,
            team1=team1,
            team2=team2,
            home=home,
            draw=draw,
            away=away,
            over=over,
            under=under,
            yes=yes,
            no=no,
            link=self._results_url
        )
        )

    def get_only_result(self):
        self._browser.get(self._results_url)
        self._results_page = BeautifulSoup(self._browser.page_source, 'html.parser')
        time.sleep(0.1)
        self._browser.refresh()
        result, amount, both = self._extract_result()
        return asdict(ResultMatchInfo(
            result=result,
            amount=amount,
            both=both,
            link=self._results_url,
        )
        )

    def get_historical_match_info(self):
        self._get_pages()
        date = self._extract_date()
        season = self._extract_season(date)
        country, league = self._extract_country_league()
        team1, team2 = self._extract_teams()
        home, draw, away = self._extract_home_draw_away()
        over, under = self._extract_over_under()
        yes, no = self._extract_both()
        result, amount, both = self._extract_result()
        return asdict(HistoricalMatchInfo(
            date=date,
            season=season,
            country=country,
            league=league,
            team1=team1,
            team2=team2,
            home=home,
            draw=draw,
            away=away,
            over=over,
            under=under,
            yes=yes,
            no=no,
            link=self._results_url,
            result=result,
            amount=amount,
            both=both,
        )
        )

    def _get_pages(self):
        self._browser.get(self._results_url)
        time.sleep(0.01)
        self._browser.refresh()
        self._results_page = BeautifulSoup(self._browser.page_source, 'html.parser')
        self._browser.get(self._amounts_url)
        time.sleep(0.01)
        self._browser.refresh()
        self._amounts_page = BeautifulSoup(self._browser.page_source, 'html.parser')
        self._browser.get(self._both_url)
        time.sleep(0.01)
        self._browser.refresh()
        self._both_page = BeautifulSoup(self._browser.page_source, 'html.parser')

    def _extract_season(self, date):
        return date.split('.')[-1]

    def _extract_country_league(self) -> tuple:
        split = self._results_url.split('/')
        return split[4], split[5]

    def _extract_date(self) -> str:
        """Получает дату матча."""
        date_class = str(self._results_page.find('p', class_='date'))
        date = date_class.split('>')[1].split('<')[0].split(',')[1]
        date_without_spaces = ' '.join(date.split())
        for key in months.keys():
            if key in date_without_spaces:
                date_without_spaces = date_without_spaces.replace(key, months[key])
        date_without_spaces = date_without_spaces.replace(' ', '.')
        return date_without_spaces

    def _extract_teams(self) -> tuple:
        """Получает названия команд."""
        title = str(self._results_page.title)
        teams = title.split('e>')[1].split('Bet')[0]
        team_1, team_2 = teams.split('-')
        return team_1.strip(), team_2.strip()

    def _extract_home_draw_away(self) -> list:
        """Получает коэффициенты на исходы."""
        aver = self._results_page.find('tr', class_='aver')
        coefs = aver.find_all('td', class_='right')
        home_draw_away = []
        for coef in coefs:
            home_draw_away.append(str(coef).split('>')[1].split('<')[0])
        return [float(elem) for elem in home_draw_away]

    def _extract_over_under(self) -> tuple:
        """Получает коэффициенты на тотал 2,5."""
        amount = str(self._amounts_page).split('P-2.50-0-0')[1]
        amount = amount.split('text">')
        return amount[2].split('<')[0], amount[1].split('<')[0]

    def _extract_both(self) -> list:
        """Получает коэффициенты на обе забьют."""
        aver = self._both_page.find('tr', class_='aver')
        coefs = aver.find_all('td', class_='right')
        home_draw_away = []
        for coef in coefs:
            home_draw_away.append(str(coef).split('>')[1].split('<')[0])
        return [float(elem) for elem in home_draw_away]

    def _extract_result(self):
        """Получает результат матча."""
        raw_result = str(self._results_page.find('p', class_='result'))
        raw_result = raw_result.split('<strong>')[1].split('</strong>')[0].split(':')
        raw_result = [int(goals) for goals in raw_result]

        if raw_result[0] == raw_result[1]:
            result = 0
        elif raw_result[0] > raw_result[1]:
            result = 1
        else:
            result = 2

        amount = raw_result[0] + raw_result[1]
        both = int(bool(raw_result[0] and raw_result[1]))
        return result, amount, both


def today_parser():
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'}
    for key in headers:
        webdriver.DesiredCapabilities.PHANTOMJS['phantomjs.page.customHeaders.{}'.format(key)] = headers[key]
    browser = webdriver.Firefox(executable_path=GECKODRIVER_PATH)

    links_parser = TodayLinksParser(browser)
    links_parser.get_links('today_links.txt')
    with open('today_links.txt', 'r') as f:
        links = f.read()

    try:
        browser.close()
    except Exception:
        print('браузер уже закрыт')

    browser = webdriver.Firefox(executable_path=GECKODRIVER_PATH)

    with open('today_match_data.txt', 'a') as f:
        for link in links.split('\n'):
            parser = Parser(browser, link)
            try:
                match_info = parser.get_match_info()
                print(match_info)
                f.write(str(match_info) + '\n')
            except Exception as exc:
                print(exc, link)

    browser.close()
    save_to_csv('today')


def date_parser(date: str):
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'}
    for key in headers:
        webdriver.DesiredCapabilities.PHANTOMJS['phantomjs.page.customHeaders.{}'.format(key)] = headers[key]

    data = pd.read_csv(f'{date}.csv')
    links = data['link'].values
    browser = webdriver.Firefox(executable_path=GECKODRIVER_PATH)
    with open(f'{date}_result_match_data.txt', 'a') as f:
        for link in links:
            link = str(link)
            parser = Parser(browser, link)
            try:
                match_info = parser.get_only_result()
                print(match_info)
                f.write(str(match_info) + '\n')
            except Exception as exc:
                print(exc, link)

    browser.close()
    save_to_csv(f'{date}_result')
    data_result = pd.read_csv(f'{date}_result.csv')
    data['result'] = data_result['result']
    data['amount'] = data_result['amount']
    data['both'] = data_result['both']
    data.to_csv(f'{date}_full.csv', index=False)


def historical_links_parser(browser, url):

    links_parser = ByLeagueLinksParser(browser, f'https://www.oddsportal.com/soccer/{url}/results')
    links_parser.get_links(f'{url}_links.txt')


def historical_match_data_parser(browser, url):

    with open(f'{url}_links.txt', 'r') as f:
        links = f.read()

    with open(f'{url}_match_data.txt', 'a') as f:
        for link in links.split('\n'):
            parser = Parser(browser, link)
            try:
                match_info = parser.get_historical_match_info()
                print(match_info)
                f.write(str(match_info) + '\n')
            except Exception as exc:
                print(exc, link)


def league_parser(league_name):
    headers = {'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_11_6) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/61.0.3163.100 Safari/537.36'}
    for key in headers:
        webdriver.DesiredCapabilities.FIREFOX['phantomjs.page.customHeaders.{}'.format(key)] = headers[key]

    league = league_name.split('/')[0]
    try:
        os.makedirs(league)
    except OSError:
        pass

    urls = [f'{league_name}-201{i}-201{i+1}' for i in range(6, 9)]
    urls.extend([f'{league_name}-2019-2020', league_name])

    for url in urls:
        try:
            browser = webdriver.Firefox(executable_path=GECKODRIVER_PATH)
            historical_links_parser(browser, url)
            try:
                browser.close()
            except Exception:
                print('браузер уже закрыт')
            browser = webdriver.Firefox(executable_path=GECKODRIVER_PATH)
            historical_match_data_parser(browser, url)
            try:
                browser.close()
            except Exception:
                print('браузер уже закрыт')
            save_to_csv(url)
        except Exception:
            print(f'Что-то не так с {url}')
            continue


if __name__ == '__main__':
    # today_parser()
    league_parser('spain/copa-del-rey')
    # date_parser('23_02_2021')
