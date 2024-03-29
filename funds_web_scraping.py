import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import Select
from selenium.common.exceptions import NoSuchElementException
import time
import re
import os
import logging
from datetime import datetime

# Logger configuration
logger = logging.getLogger(__name__)
logger.setLevel(logging.DEBUG)
formater = logging.Formatter('[%(asctime)s] - %(levelname)s - %(message)s')
fh = logging.FileHandler('./logs/data_processing'+datetime.today().strftime('%Y%m%d')+'.log')# , mode='w')
fh.setFormatter(formater)
logger.addHandler(fh)

def selecting_fund(select, value_to_select):
    """function that selects an investment fund by value on a webpage's dropdown """

    # select by value
    select.select_by_value(value_to_select)
    time.sleep(3)

    html = browser.page_source

    return html


def open_excel(excel_path):
    saved_data = pd.read_excel(excel_path)
    return saved_data


def get_browser(URL):
    options =Options()
    options.add_argument("--headless")  # To Avoid the navigator to open

    browser = webdriver.Chrome(options=options, executable_path=r'D:\Giovanny\Inversiones\chromedriver.exe')

    return browser


def backup_data(df, path):
    backup_path = os.path.join(path, 'backup', 'investment_funds.xlsx')
    df.to_excel(backup_path, index=False)


def bancolombia_web_scraping(browser, site_url, cwd):
    browser.get(site_url)
    time.sleep(3)
    default_html = browser.page_source

    historical_path = os.path.join(cwd, 'investment_funds.xlsx')

    soup = BeautifulSoup(default_html, 'lxml')

    # Find select tag
    select_tag = soup.find("select")

    # find all option tag inside select tag
    options = select_tag.find_all("option")
    options_dict = {}

    # Iterate through all option tags and get inside text
    for i, option in enumerate(options):
        # Using a regular expression to extract the value of the option
        option_value = re.findall('\"([0-9]{1,2})', str(option))[0]
        option_text = option.text
        if option_text not in options_dict.values():
            options_dict[option_value] = option_text
            logger.debug(f'{option_value} {option_text}')
        else:
            continue

    element_dropdown = browser.find_element_by_name('nmSelectFondo')
    select = Select(element_dropdown)

    historical_df = open_excel(historical_path)

    temp = pd.DataFrame(columns=historical_df.columns)

    for val in options_dict.keys():
        fund_to_select = val

        logger.debug('Extracting information for: ' + options_dict[val])

        html = selecting_fund(select, fund_to_select)

        soup = BeautifulSoup(html, 'lxml')

        df = pd.read_html(html)

        try:
            df = pd.DataFrame(df[0])  # when the base web page is grupobancolombia
            # df = pd.DataFrame(df[2]) # when the base web page is valores.grupobancolombia

            general_info_df = df.loc[:4, :].T
            general_info_df = general_info_df.loc[~general_info_df.duplicated(keep='first'), :].T
            general_info_df.columns = ['parameter', 'value']
            general_info_df.value.fillna('No aplica', inplace=True)

            days_profitability_df = df.loc[7:8, :].T
            days_profitability_df.columns = ['parameter', 'value']

            years_profitability_df = df.loc[10:11, :].T
            years_profitability_df.columns = ['parameter', 'value']

            closing_date_df = df.loc[13:14, :].T
            closing_date_df = closing_date_df.loc[~closing_date_df.duplicated(keep='first'), :].T
            closing_date_df.columns = ['parameter', 'value']

            fund_info = pd.concat([general_info_df, days_profitability_df, years_profitability_df, closing_date_df])

            fund_info.value = fund_info.value.str.replace('$', '')
            fund_info.value = fund_info.value.str.replace('%', '')

            key_list = fund_info.parameter.tolist()
            key_list.append('Fondo de Inversion')
            value_list = fund_info.value.tolist()
            value_list.append(options_dict[fund_to_select])
            value_list = [[x] for x in value_list]
            fund_info_dict = dict(zip(key_list, value_list))

            current_fund_info = pd.DataFrame(data=fund_info_dict)

            current_fund_info['Valor en Pesos'] = current_fund_info['Valor en Pesos'].str \
                .replace(',', '').astype('float')

            if current_fund_info['Fondo administrador por'].str.contains('Fiduciaria').any():
                str_columns = ['7 días', '30 días', '180 días', 'Año corrido',
                               'Último año', 'Últimos dos años', 'Últimos tres años']
                current_fund_info['Valor de la unidad'] = current_fund_info['Valor de la unidad'].str. \
                                                              replace(',', '').astype('float') * 1000
                current_fund_info[str_columns] = current_fund_info[str_columns].apply(lambda x: x.str.replace('.', ''),
                                                                                      axis=0)
                current_fund_info[str_columns] = current_fund_info[str_columns].apply(lambda x: x.str.replace(',', '.'),
                                                                                      axis=0)
            else:
                str_columns = ['Valor de la unidad', '7 días', '30 días', '180 días', 'Año corrido',
                               'Último año', 'Últimos dos años', 'Últimos tres años']
                current_fund_info[str_columns] = current_fund_info[str_columns].apply(lambda x: x.str.replace(',', ''),
                                                                                      axis=0)

            # Useful when some fund have a wrong % number on the web
            # try:
            #    current_fund_info[str_columns] = current_fund_info[str_columns].apply(lambda x : x.astype('float') 
            #                                                                    if ~x.str.contains('N/A').any() 
            #                                                                    else x.astype('object'), axis = 0)
            # except:
            #    pass        

            current_fund_info[str_columns] = current_fund_info[str_columns]. \
                apply(lambda x: x.astype('float') if ~x.str.contains('N/A').any() else x.astype('object'), axis=0)

            current_fund_info['Fecha de Cierre'] = pd.to_datetime(current_fund_info['Fecha de Cierre'],
                                                                  format='%Y/%m/%d')
            current_fund_info['Fecha Extracción'] = pd.to_datetime(time.strftime('%Y/%m/%d',
                                                                                 time.localtime(time.time())))

            # Re ordering the columns
            current_fund_info = current_fund_info[
                ['Fondo de Inversion', 'Fecha Extracción', 'Valor de la unidad', 'Valor en Pesos', '7 días', '30 días',
                 '180 días', 'Año corrido', 'Último año', 'Últimos dos años', 'Últimos tres años', 'Fecha de Cierre',
                 'Fondo administrador por', 'Calificación', 'Plazo', ]
            ]

            temp = pd.concat([temp, current_fund_info])
            logger.debug(f'Successfully extracted data for: {options_dict[val]}')
        except Exception as e:
            logger.error(f'Error: {e}')
            continue

    browser.quit()

    # Appending new data to the historial dataset
    historical_df = pd.concat([historical_df, temp]).reset_index(drop=True)
    historical_df = historical_df[['Fondo de Inversion', 'Fecha Extracción', 'Valor de la unidad', 'Valor en Pesos',
                                   '7 días', '30 días', '180 días', 'Año corrido', 'Último año', 'Últimos dos años',
                                   'Últimos tres años', 'Fecha de Cierre', 'Fondo administrador por', 'Calificación',
                                   'Plazo']]

    logger.debug('upgrading file...')
    historical_df.to_excel(historical_path, index=False)
    backup_data(historical_df, cwd)
    logger.debug('file successfully upgraded')


def credicorp_web_scraping(browser, site_url, key, idx_df1, idx_df2, cwd):
    browser.get(site_url)
    time.sleep(2)
    default_html = browser.page_source

    historical_path = os.path.join(cwd, 'investment_funds.xlsx')

    soup = BeautifulSoup(default_html, 'lxml')

    historical_df = open_excel(historical_path)

    df = pd.read_html(default_html)

    closing_date_df = pd.DataFrame(df[idx_df1]).loc[0, :].T

    fund_value_df = pd.DataFrame(df[idx_df1]).loc[1, :].T

    fund_info = pd.concat([pd.DataFrame(df[idx_df2]).loc[0:1, :], closing_date_df, fund_value_df], axis=1)

    fund_info.columns = fund_info.loc[0, :]
    fund_info.drop(0, axis=0, inplace=True)

    fund_info['Fondo de Inversion'] = key
    fund_info['Calificación'] = 'No Aplica'
    fund_info['Plazo'] = 'No aplica'
    fund_info['Fondo administrador por'] = 'Credicorp Capital'
    fund_info['7 días'] = np.nan

    fund_info.drop(['Tipo de participación', 'Valor TP (en MM)'], axis=1, inplace=True)

    fund_info.rename(columns={'Valor Unidad TP': 'Valor de la unidad',
                              'Último Mes': '30 días',
                              'Últimos 6 Meses': '180 días',
                              'Año Corrido': 'Año corrido',
                              'Último Año': 'Último año',
                              'Últimos 2 Años': 'Últimos dos años',
                              'Últimos 3 Años': 'Últimos tres años',
                              'Fecha Cierre': 'Fecha de Cierre',
                              'Valor del Fondo': 'Valor en Pesos'}
                     , inplace=True)

    fund_info = fund_info.apply(lambda x: x.str.replace('$', '') if x.dtype == 'object' else x, axis=0)
    fund_info = fund_info.apply(lambda x: x.str.replace('%', '') if x.dtype == 'object' else x, axis=0)
    fund_info = fund_info.apply(lambda x: x.str.replace(',', '') if x.dtype == 'object' else x, axis=0)

    float_columns = ['Valor de la unidad', '30 días', '180 días', 'Año corrido', 'Último año', 'Últimos dos años',
                     'Últimos tres años', 'Valor en Pesos']

    fund_info[float_columns] = fund_info[float_columns].apply(lambda x: x.astype('float'), axis=0)

    fund_info['Fecha de Cierre'] = pd.to_datetime(fund_info['Fecha de Cierre'], format='%Y/%m/%d')
    fund_info['Fecha Extracción'] = pd.to_datetime(time.strftime('%Y/%m/%d', time.localtime(time.time())))

    # Re ordering the columns
    fund_info = fund_info[['Fondo de Inversion', 'Fecha Extracción', 'Valor de la unidad', 'Valor en Pesos', '7 días',
                           '30 días', '180 días', 'Año corrido', 'Último año', 'Últimos dos años', 'Últimos tres años',
                           'Fecha de Cierre', 'Fondo administrador por', 'Calificación', 'Plazo', ]]

    browser.quit()

    historical_df = pd.concat([historical_df, fund_info]).reset_index(drop=True)

    logger.debug('upgrading file...')
    historical_df.to_excel(historical_path, index=False)
    backup_data(historical_df, cwd)
    logger.debug('file successfully upgraded')


if __name__ == "__main__":

    cwd = r'D:\Giovanny\Inversiones'

    bancolombia_site_url = 'https://www.grupobancolombia.com/personas/productos-servicios/inversiones/fondos-' \
                           'inversion-colectiva/aplicacion-fondos/'
    # bancolombia_site_url = 'https://valores.grupobancolombia.com/wps/portal/valores-bancolombia/productos-
    # servicios/fondos-inversion-colectiva/aplicacion-fondos'

    credicorp_sites_url = {'Acciones Globales': {'url': 'https://www.credicorpcapital.com/Colombia/Neg/GA/Paginas/FGA.aspx',
                                                 'idx_df1': 1,
                                                 'idx_df2': 2},
                           'Renta Fija Global': {'url': 'https://www.credicorpcapital.com/Colombia/Neg/GA/Paginas/FGRF.aspx',
                                                 'idx_df1': 1,
                                                 'idx_df2': 2},
                           'Deuda Corporativa': {'url':'https://www.credicorpcapital.com/Colombia/Neg//GA/Paginas/DCF.aspx',
                                                 'idx_df1': 1,
                                                 'idx_df2': 2},
                           'Alta Liquidez': {'url':  'https://www.credicorpcapital.com/Colombia/Neg/GA/Paginas/CCAL.aspx',
                                             'idx_df1': 0,
                                             'idx_df2': 1},
                           'Renta Fija Colombia': {'url': 'https://www.credicorpcapital.com/Colombia/Neg/GA/Paginas/FR-FC.aspx',
                                                   'idx_df1': 0,
                                                   'idx_df2': 1},
                           'Acciones Colombia': {'url': 'https://www.credicorpcapital.com/Colombia/Neg/GA/Paginas/FAD.aspx',
                                                 'idx_df1': 1,
                                                 'idx_df2': 2}}

    # Get the browser for the bancolombia url
    browser = get_browser(bancolombia_site_url)

    bancolombia_web_scraping(browser, bancolombia_site_url, cwd)

    # Iterating through the credicorp investment funds
    for key in credicorp_sites_url:
        # Get the browser for the credicorp url
        browser = get_browser(credicorp_sites_url[key]['url'])
        try:
            credicorp_web_scraping(browser, credicorp_sites_url[key]['url'], key, credicorp_sites_url[key]['idx_df1'],
                                   credicorp_sites_url[key]['idx_df2'], cwd)
        except Exception as e:
            logger.error(f'Error processing data for {key}: {e}')
            continue
