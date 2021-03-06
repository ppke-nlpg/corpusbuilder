#!/usr/bin/env python3
# -*- coding: utf-8, vim: expandtab:ts=4 -*-

import os
import re
import sys
import yaml
import logging
from datetime import date, timedelta, datetime


def wrap_input_consants(current_task_config_filename):
    """
        Helper to store and process input data so that main function does not contain so many
         codelines of variable initialization
        Fields should be handled as constants after initialization
         CAPITALIZED KEYS are transformed runtime (e.g. Regular Expressions),
         lowercase keys are present in the config and will be used as is
    """
    # Instructions to the current task
    with open(current_task_config_filename, encoding='UTF-8') as fh:
        settings = yaml.load(fh)

    # The directory name of the configs
    dir_name = os.path.dirname(os.path.abspath(current_task_config_filename))

    # Technical data about the website to crawl
    with open(os.path.join(dir_name, settings['site_schemas']), encoding='UTF-8') as fh:
        current_site_schema = yaml.load(fh)[settings['site_name']]

    if len(settings.keys() & current_site_schema.keys()) > 0:
        raise KeyError('Config file key collision!')
    settings.update(current_site_schema)

    settings['TAGS_KEYS'] = {re.compile(tag_key): val for tag_key, val in settings['tags_keys'].items()}

    # If the program is to create a corpus, then it will load the required tags and compile the REs
    if settings['create_corpus']:
        with open(os.path.join(dir_name, settings['tags']), encoding='UTF-8') as fh:
            all_tags = yaml.load(fh)
            common_tags = all_tags['common']

        cleaning_rules = {}
        general_cleaning_rules = common_tags.pop('general_cleaning_rules', {})  # Also remove general rules from common!
        for rule, regex in ((rule, regex) for rule, regex in general_cleaning_rules.items()
                            if not rule.endswith('_repl')):
            r = re.compile(regex)
            cleaning_rules[rule] = lambda x: r.sub(general_cleaning_rules['{0}_repl'.format(rule)], x)

        site_tags = {}
        for tag_key_readable in settings['TAGS_KEYS'].values():
            site_tags[tag_key_readable] = {}
            if tag_key_readable is not None:  # None == Explicitly ignored
                for tag_name, tag_desc in all_tags[tag_key_readable].items():
                    site_tags[tag_key_readable][tag_name] = {}
                    site_tags[tag_key_readable][tag_name]['open-inside-close'] = re.compile('{0}{1}{2}'.
                                                                                            format(tag_desc['open'],
                                                                                                   tag_desc['inside'],
                                                                                                   tag_desc['close']))
                    site_tags[tag_key_readable][tag_name]['open'] = re.compile(tag_desc['open'])
                    site_tags[tag_key_readable][tag_name]['close'] = re.compile(tag_desc['close'])

    else:
        site_tags = {}
        common_tags = {'article_begin_mark': '', 'article_end_mark': ''}
        cleaning_rules = {}
    settings['SITE_TAGS'] = site_tags
    settings['COMMON_SITE_TAGS'] = common_tags
    settings['GENERAL_CLEANING_RULES'] = cleaning_rules

    settings['BEFORE_ARTICLE_URL_RE'] = re.compile(current_site_schema['before_article_url'])
    settings['AFTER_ARTICLE_URL_RE'] = re.compile(current_site_schema['after_article_url'])
    settings['ARTICLE_URL_FORMAT_RE'] = re.compile('{0}{1}{2}'.format(current_site_schema['before_article_url'],
                                                                      current_site_schema['article_url_format'],
                                                                      current_site_schema['after_article_url']))

    settings['BEFORE_NEXT_PAGE_URL_RE'] = re.compile(current_site_schema['before_next_page_url'])
    settings['AFTER_NEXT_PAGE_URL_RE'] = re.compile(current_site_schema['after_next_page_url'])
    settings['NEXT_PAGE_URL_FORMAT_RE'] = re.compile('{0}{1}{2}'.format(current_site_schema['before_next_page_url'],
                                                                        current_site_schema['next_page_url_format'],
                                                                        current_site_schema['after_next_page_url']))

    settings['BEFORE_ARTICLE_DATE_RE'] = re.compile(current_site_schema['before_article_date'])
    settings['AFTER_ARTICLE_DATE_RE'] = re.compile(current_site_schema['after_article_date'])
    settings['ARTICLE_DATE_FORMAT_RE'] = re.compile('{0}{1}{2}'.format(current_site_schema['before_article_date'],
                                                                       current_site_schema['article_date_format'],
                                                                       current_site_schema['after_article_date']))

    settings['filter_articles_by_date'] = False
    if 'date_from' in settings and 'date_until' in settings:
        # We generate all URLs FROM the past UNTIL the "not so past"
        # Raises ValueError if there is something wrong
        if isinstance(settings['date_from'], datetime):
            raise ValueError('DateError: date_from not datetime ({0})!'.format(settings['date_from']))
        if isinstance(settings['date_until'], datetime):
            raise ValueError('DateError: date_until not datetime ({0})!'.format(settings['date_until']))
        if settings['date_from'] > settings['date_until']:
            raise ValueError('DateError: date_from is later than DATE UNTIL!')

        settings['filter_articles_by_date'] = True  # Date filtering ON in any other cases OFF

    # if there is no time filtering then we use dates only if they are needed to generate URLs
    elif settings['archive_page_urls_by_date']:
        if 'date_from' in settings:
            # We generate all URLs from the first day of the website until yesterday
            if isinstance(settings['date_from'], datetime):
                raise ValueError('DateError: date_from not datetime ({0})!'.format(settings['date_from']))
        else:
            settings['date_from'] = current_site_schema['date_first_article']
            if isinstance(current_site_schema['date_first_article'], datetime):
                raise ValueError('DateError: date_first_article not datetime ({0})!'.
                                 format(current_site_schema['date_first_article']))
        settings['date_until'] = date.today() - timedelta(1)  # yesterday

        if settings['date_from'] > settings['date_until']:
            raise ValueError('DateError: date_from is later than DATE UNTIL!')

    return settings


class Logger:
    """
        Handle logging with Python's built-in logging facilities simplified
    """
    def __init__(self, log_filename, console_level='INFO', console_stream=sys.stderr,
                 logfile_level='INFO', logfile_mode='a', logfile_encoding='UTF-8'):
        # logging.basicConfig(level=logging.INFO)
        log_levels = {'DEBUG': logging.DEBUG, 'INFO': logging.INFO, 'WARNING': logging.WARNING, 'ERROR': logging.ERROR,
                      'CRITICAL': logging.CRITICAL}

        if console_level not in log_levels:
            raise KeyError('Console loglevel is not valid ({0}): {1}'.format(', '.join(log_levels.keys()),
                                                                             console_level))
        if logfile_level not in log_levels:
            raise KeyError('Logfile loglevel is not valid ({0}): {1}'.format(', '.join(log_levels.keys()),
                                                                             logfile_level))

        # Create logger
        self._logger = logging.getLogger(log_filename)  # Logger is named after the logfile
        self._logger.propagate = False

        # Create handler one for console output and one for logfile and set their properties accordingly
        c_handler = logging.StreamHandler(stream=console_stream)
        f_handler = logging.FileHandler(log_filename, mode=logfile_mode, encoding=logfile_encoding)
        c_handler.setLevel(console_level)
        f_handler.setLevel(logfile_level)

        # Create formatters and add them to handlers
        c_format = logging.Formatter('{asctime} {levelname}: {message}', style='{')
        f_format = logging.Formatter('{asctime} {levelname}: {message}', style='{')
        c_handler.setFormatter(c_format)
        f_handler.setFormatter(f_format)

        # Add handlers to the logger
        self._logger.addHandler(c_handler)
        self._logger.addHandler(f_handler)
        if console_level < logfile_level:
            self._logger.setLevel(console_level)
        else:
            self._logger.setLevel(logfile_level)

        self._leveled_logger = {'DEBUG': self._logger.debug, 'INFO': self._logger.info, 'WARNING': self._logger.warning,
                                'ERROR': self._logger.error, 'CRITICAL': self._logger.critical}

        self.log('INFO', 'Logging started')

    def log(self, level, msg):
        if level in self._leveled_logger:
            self._leveled_logger[level](msg)
        else:
            self._leveled_logger['CRITICAL']('UNKNOWN LOGGING LEVEL SPECIFIED FOR THE NEXT ENTRY: {0}'.format(level))
            self._leveled_logger['CRITICAL'](msg)

    def __del__(self):
        handlers = list(self._logger.handlers)
        for h in handlers:
            self._logger.removeHandler(h)
            h.flush()
            if isinstance(h, logging.FileHandler):
                h.close()
