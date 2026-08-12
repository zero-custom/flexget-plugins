"""regexp_nest - regexp filter plugin with nested ``within`` sub-patterns."""

import re
from urllib.parse import unquote

from loguru import logger

from flexget import plugin
from flexget.config_schema import one_or_more
from flexget.entry import Entry
from flexget.event import event

logger = logger.bind(name='regexp_nest')


class FilterRegexpNest:
    """All possible forms, with nested ``within`` sub-pattern routing.

    Configuration options::

        regexp_nest:
          [operation]:           # operation to perform on matches
            - [regexp]           # simple regexp
            - [regexp]: <path>   # override path
            - [regexp]:
                [path]: <path>   # override path
                [not]: <regexp>  # not match
                [from]: <field>  # search from given entry field
                [within]:        # nested sub-patterns (regexp_nest addition)
                  - [regexp]:
                      [path]: <path>
                      [within]: ...   # recurses
            - [regexp]:
                [path]: <path>   # override path
                [not]:           # list of not match regexps
                  - <regexp>
                [from]:          # search only from these fields
                  - <field>
          [operation]:
            - <regexp>
          [rest]: <operation>    # non matching entries are
          [from]:                # search only from these fields for all regexps
            - <field>

    Possible operations: accept, reject, accept_excluding, reject_excluding
    """

    schema = {
        'type': 'object',
        'properties': {
            'accept': {'$ref': '#/$defs/regex_list'},
            'reject': {'$ref': '#/$defs/regex_list'},
            'accept_excluding': {'$ref': '#/$defs/regex_list'},
            'reject_excluding': {'$ref': '#/$defs/regex_list'},
            'rest': {'type': 'string', 'enum': ['accept', 'reject']},
            'from': one_or_more({'type': 'string'}),
        },
        'additionalProperties': False,
        '$defs': {
            # The validator for a list of regexps, each with or without settings
            'regex_list': {
                'type': 'array',
                'items': {
                    'oneOf': [
                        # Plain regex string
                        {'type': 'string', 'format': 'regex'},
                        # Regex with options (regex is key, options are value)
                        {
                            'type': 'object',
                            'additionalProperties': {
                                'oneOf': [
                                    # Simple options, just path
                                    {'type': 'string', 'format': 'path'},
                                    # Dict style options; within holds nested sub-patterns (regexp_nest addition)
                                    {
                                        'type': 'object',
                                        'properties': {
                                            'path': {'type': 'string', 'format': 'path'},
                                            'set': {'type': 'object'},
                                            # Recursive sub-patterns (regexp_nest addition)
                                            'within': {'$ref': '#/$defs/regex_list'},
                                            'not': one_or_more({
                                                'type': 'string',
                                                'format': 'regex',
                                            }),
                                            'from': one_or_more({'type': 'string'}),
                                        },
                                        'additionalProperties': False,
                                    },
                                ]
                            },
                        },
                    ]
                },
            }
        },
    }

    def prepare_config(self, config):
        """Return the config in a normalized, recursively-compiled form.

        Every regexp item becomes a dict::

            {'regexp': <compiled regex>, 'opts': {...}, 'within': [<item>, ...]}

        where ``within`` holds the recursively prepared nested items.
        """
        out_config = {}
        if 'rest' in config:
            out_config['rest'] = config['rest']
        # Turn all our regexps into advanced form dicts and compile them
        for operation, regexps in config.items():
            if operation in ['rest', 'from']:
                continue
            for regexp_item in regexps:
                out_config.setdefault(operation, []).append(
                    self._prepare_item(regexp_item, config)
                )
        return out_config

    def _prepare_item(self, regexp_item, config):
        """Compile a single (possibly nested) regexp item into normalized form."""
        if not isinstance(regexp_item, dict):
            regexp = regexp_item
            opts = {}
        else:
            regexp, _opts = next(iter(regexp_item.items()))
            opts = _opts if isinstance(_opts, dict) else {'path': _opts}

        opts = opts.copy()
        # Parse custom settings for this regexp, and we don't want to modify original config
        # advanced configuration
        if config.get('from'):
            opts.setdefault('from', config['from'])
        # Put plain strings into list form for `from` and `not` options
        if 'from' in opts and isinstance(opts['from'], str):
            opts['from'] = [opts['from']]
        if 'not' in opts and isinstance(opts['not'], str):
            opts['not'] = [opts['not']]

        # compile `not` option regexps
        if 'not' in opts:
            opts['not'] = [re.compile(n, re.IGNORECASE) for n in opts['not']]

        # recursively compile the nested `within` sub-patterns (regexp_nest addition)
        within = [self._prepare_item(child, config) for child in opts.pop('within', [])]

        # compile regexp and make sure regexp is a string for series like '24'
        try:
            regexp = re.compile(str(regexp), re.IGNORECASE)
        except re.error as e:
            # Since validator can't validate dict keys (when an option is defined for the pattern) make sure we
            # raise a proper error here.
            raise plugin.PluginError(f'Invalid regex `{regexp}`: {e}')
        return {'regexp': regexp, 'opts': opts, 'within': within}

    def matches(self, entry, regexp, find_from=None, not_regexps=None):
        """Check if :entry: has any string fields / list-field strings matching :regexp:.

        :param entry: Entry instance
        :param regexp: Compiled regexp
        :param find_from: None or a list of fields to search from
        :param not_regexps: None or list of regexps that must NOT match
        :return: Field matched, or None
        """
        unquote_fields = ['url']
        for field in find_from or ['title', 'description']:
            # Only evaluate lazy fields if find_from has been explicitly specified
            if not entry.get(field, eval_lazy=find_from):
                continue
            # Make all fields into lists for search purposes
            values = entry[field]
            if not isinstance(values, list):
                values = [values]
            for value in values:
                if not isinstance(value, str):
                    value = str(value)
                if field in unquote_fields:
                    value = unquote(value)
                if regexp.search(value):
                    # Make sure the not_regexps do not match for this field
                    for not_regexp in not_regexps or []:
                        if self.matches(entry, not_regexp, find_from=[field]):
                            break
                    else:  # None of the not_regexps matched
                        return field
        return None

    def route(self, entry, item):
        """Return the deepest matching ``path`` for this item, or None.

        The base ``path`` is overridden by the deepest matching ``within``
        sub-pattern's path (regexp_nest addition).
        """
        regexp = item['regexp']
        opts = item['opts']
        if not self.matches(entry, regexp, opts.get('from'), opts.get('not')):
            return None
        path = opts.get('path')
        # descend into nested `within` sub-patterns; the deepest match wins (regexp_nest addition)
        for child in item['within']:
            child_path = self.route(entry, child)
            if child_path is not None:
                path = child_path
        return path

    def apply_set(self, entry, item):
        """Apply ``set`` options along the matching branch chain.

        Returns True if this item (or one of its ``within`` children) matched.
        """
        regexp = item['regexp']
        opts = item['opts']
        if not self.matches(entry, regexp, opts.get('from'), opts.get('not')):
            return False
        if opts.get('set'):
            # invoke set plugin with given configuration
            logger.debug('adding set: info to entry:"{}" {}', entry['title'], opts['set'])
            plugin.get('set', self).modify(entry, opts['set'])
        # descend into nested `within` sub-patterns (regexp_nest addition)
        for child in item['within']:
            self.apply_set(entry, child)
        return True

    def filter(self, entries, operation, regexps):
        """Return set of entries that matched regexps.

        :param entries: entries to filter
        :param operation: one of ``accept`` ``reject`` ``accept_excluding`` and ``reject_excluding``
                          accept and reject will be called on the entry if any of the regexps match
                          ``*_excluding`` operations will be called if any of the regexps don't match
        :param regexps: list of normalized {regexp, opts, within} items
        :return: set of matched entries
        """
        matched = set()
        method = Entry.accept if 'accept' in operation else Entry.reject
        match_mode = 'excluding' not in operation
        for entry in entries:
            for item in regexps:
                if match_mode:
                    hit = self.apply_set(entry, item)
                    if hit:
                        # route the entry to its deepest matching path
                        path = self.route(entry, item)
                        if path:
                            entry['path'] = path
                            logger.debug('regexp_nest: routed {} to {}', entry['title'], path)
                else:
                    hit = self.route(entry, item) is not None
                    if not hit:
                        # keep the built-in behavior: apply this item's own path/set
                        # even when the entry does not match
                        opts = item['opts']
                        if opts.get('path'):
                            entry['path'] = opts['path']
                        if opts.get('set'):
                            # invoke set plugin with given configuration
                            plugin.get('set', self).modify(entry, opts['set'])
                # Run if we are in match mode and have a hit, or are in non-match mode and don't have a hit
                if match_mode == hit:
                    # Creates the string with the reason for the hit
                    matchtext = f"regexp '{item['regexp'].pattern}' " + (
                        f"matched" if match_mode else "didn't match"
                    )
                    logger.debug('{} for {}', matchtext, entry['title'])
                    method(entry, matchtext)
                    matched.add(entry)
                    # We had a match so break out of the regexp loop.
                    break
            else:
                # We didn't run method for any of the regexps, add this entry to rest
                entry.trace(f'None of configured {operation} regexps matched')
        return matched

    @plugin.priority(172)
    def on_task_filter(self, task, config):
        config = self.prepare_config(config)
        # Keep track of all entries which have not matched any regexp
        rest = set(task.entries)
        for operation, regexps in config.items():
            if operation == 'rest':
                continue
            matched = self.filter(task.entries, operation, regexps)
            # Remove any entries from rest which matched this regexp
            rest -= matched

        if 'rest' in config:
            rest_method = Entry.accept if config['rest'] == 'accept' else Entry.reject
            for entry in rest:
                logger.debug('Rest method {} for {}', config['rest'], entry['title'])
                rest_method(entry, 'regexp `rest`')


@event('plugin.register')
def register_plugin():
    plugin.register(FilterRegexpNest, 'regexp_nest', api_ver=2)