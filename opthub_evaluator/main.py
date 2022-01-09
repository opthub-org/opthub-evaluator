# coding: utf-8
"""
Definition of CLI commands.
"""
import json
import logging
from os import path
from traceback import format_exc
from time import sleep

import click
from click.types import StringParamType
import docker
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport
import yaml


_logger = logging.getLogger(__name__)


class AliasedGroup(click.Group):
    """A Click group with short subcommands.

    Example
    -------
    >>> @click.command(cls=AliasedGroup)
    >>> def long_name_command():
    ...     pass
    """

    def get_command(self, ctx, cmd_name):
        rv = click.Group.get_command(self, ctx, cmd_name)
        if rv is not None:
            return rv
        matches = [x for x in self.list_commands(ctx)
                   if x.startswith(cmd_name)]
        if not matches:
            return None
        elif len(matches) == 1:
            return click.Group.get_command(self, ctx, matches[0])
        ctx.fail('Too many matches: %s' % ', '.join(sorted(matches)))


class StrLength(StringParamType):
    """A Click option type of string with length validation.

    This is basically the same as `str`, except for additional
    functionalities of length validation.

    :param min: Minimum length
    :param max: Maximum length
    :param clamp: Clamp the input if exeeded
    """

    def __init__(self, min=None, max=None, clamp=False):
        self.min = min
        self.max = max
        self.clamp = clamp

    def convert(self, value, param, ctx):
        rv = StringParamType.convert(self, value, param, ctx)
        l = len(rv)
        if self.clamp:
            if self.min is not None and l < self.min:
                return rv + ' ' * (self.min - l)
            if self.max is not None and l > self.max:
                return rv[:self.max]
        if self.min is not None and l < self.min or \
           self.max is not None and l > self.max:
            if self.min is None:
                self.fail(
                    'Length %d is longer than the maximum valid length %d.'
                    % (l, self.max), param, ctx)
            elif self.max is None:
                self.fail(
                    'Length %d is shorter than the minimum valid length %d.'
                    % (l, self.min), param, ctx)
            else:
                self.fail(
                    'Length %d is not in the valid range of %d to %d.'
                    % (l, self.min, self.max), param, ctx)
        return rv

    def __repr__(self):
        return 'StrLength(%d, %d)' % (self.min, self.max)


def load_config(ctx, self, value):
    """Load `ctx.default_map` from a file.

    :param ctx: Click context
    :param self: Self object
    :param value: File name
    :return dict: Loaded config
    """

    if not path.exists(value):
        return {}
    with open(value) as f:
        ctx.default_map = yaml.safe_load(f)
    return ctx.default_map


def save_config(ctx, value):
    """Save `ctx.default_map` to a file.

    :param ctx: Click context
    :param value: File name
    :return dict: Saveed config
    """

    with open(value, 'w') as f:
        yaml.dump(ctx.default_map, f)
    return ctx.default_map


def query(ctx, q, **kwargs):
    """Submit a GraphQL query to a database.

    :param ctx: Click context
    :param q: str: GraphQL query submitted to a database. q takes either of q_solution_to_evaluate, q_start_evaluation, q_check_budget, q_finish_evaluation, q_cancel_evaluation.
    :param kwargs: GraphQL variables
    :return r: Results returned from a query (q). r depends on q. For example, when q=q_solution_to_evaluate, r is about a single solution that has not been evaluated by objective functions.
    """    
    _logger.debug('query(%s, %s)', q, kwargs)
    try:
        r = ctx.obj['client'].execute(gql(q), variable_values=kwargs)
    except Exception as e:
        ctx.fail('Exception %s raised when executing query %s\n' % (e, q))
    _logger.debug('-> %s', r)
    return r


def wait_to_fetch(ctx, interval):
    """Check if an unevaluated solution exists in a database by calling query every "interval" seconds.

    :param ctx: Click context
    :param interval: int: Interval to access a database (second)
    :return solution_id: ID of a solution that has not been evaluated.
    """    
    while True:
        r = query(ctx, q_solution_to_evaluate)  # Polling
        if r['solutions']:
            break  # solution found
        sleep(interval)
    return r['solutions'][0]['id']


def check_budget(ctx, user_id, match_id):
    r = query(ctx, q_check_budget, user_id=user_id, match_id=match_id)
    p = r['progress'][0]
    n_eval = p['submitted'] - p['evaluation_error'] - p['scoring_error']
    if n_eval > p['budget']:  # Budget exceeded.
        raise Exception('Out of budget: %d / %d.' % (n_eval, p['budget']))


# Check if an unevaluated solution exists in a database.
q_solution_to_evaluate = """
query solution_to_evaluate {
  solutions(
    limit: 1
    order_by: { id: asc }
    where: { evaluation_started_at: { _is_null: true } }
  ) {
    id
  }
}
"""

# Update evaluation_started_at of a solution to be evaluated by objective functions to the current time now().
q_start_evaluation = """
mutation start_evaluation(
  $id: Int!
) {
  update_solutions(
    where: {
      id: { _eq: $id }
      evaluation_started_at: { _is_null: true }
    }
    _set: {
      evaluation_started_at: "now()"
    }
  ) {
    affected_rows
    returning {
      id
      owner_id
      match_id
      match {
        problem { image }
        environments {
          key
          value
        }
      }
      variable
    }
  }
}
"""

# Get information about the number of function evaluations so far. budget is the pre-defined maximum number of function evaluations for a given problem instance. submitted is the total number of submissions of solutions. evaluation_error is the number of errors that occurred during the evaluation process. scoring_error is the number of errors that occurred during the scoring process.
q_check_budget = """
query check_budget(
    $user_id: String!
    $match_id: Int!
) {
  progress(
    limit: 1
    where: {
        user_id: { _eq: $user_id }
        match_id: { _eq: $match_id }
    }
  ) {
    budget
    submitted
    evaluating
    evaluated
    evaluation_error
    scoring
    scored
    scoring_error
  }
}
"""

# Update evaluation_finished_at to the current time now(). Objective values, constraint values, and information about errors are also updated.
q_finish_evaluation = """
mutation finish_evaluation(
    $id: Int!
    $objective: jsonb
    $constraint: jsonb
    $info: jsonb
    $error: String
) {
  update_solutions_by_pk(
    pk_columns: { id: $id }
    _set: {
      objective: $objective
      constraint: $constraint
      info: $info
      evaluation_error: $error
      evaluation_finished_at: "now()"
    }) {
    id
    updated_at
  }
}
"""

# Update evaluation_started_at and evaluation_finished_at to null when an error occurs in the evaluation process. A solution with evaluation_started_at=null and evaluation_finished=null means that it has not been evaluated by objective functions.
q_cancel_evaluation = """
mutation cancel_evaluation(
  $id: Int!
) {
  update_solutions_by_pk(
    pk_columns: { id: $id }
    _set: {
      objective: null
      constraint: null
      info: null
      evaluation_started_at: null
      evaluation_finished_at: null
    }) {
    id
    updated_at
  }
}
"""


@click.command(help='OptHub Evaluator.')
@click.option('-u', '--url', envvar='OPTHUB_URL', type=str,
              default='https://opthub-api.herokuapp.com/v1/graphql',
              help='URL to OptHub.')
@click.option('-a', '--apikey', envvar='OPTHUB_APIKEY',
              type=StrLength(max=64), help='ApiKey.')
@click.option('-i', '--interval', envvar='OPTHUB_INTERVAL',
              type=click.IntRange(min=1), default=2, help='Polling interval.')
@click.option('--verify/--no-verify', envvar='OPTHUB_VERIFY',
              default=True, help='Verify SSL certificate.')
@click.option('-r', '--retries', envvar='OPTHUB_RETRIES',
              type=click.IntRange(min=0), default=3,
              help='Retries to establish HTTPS connection.')
@click.option('-t', '--timeout', envvar='OPTHUB_TIMEOUT',
              type=click.IntRange(min=0), default=600,
              help='Timeout to process a query.')
@click.option('--rm', envvar='OPTHUB_REMOVE',
              is_flag=True,
              help='Remove containers after exit.')
@click.option('-q', '--quiet', count=True, help='Be quieter.')
@click.option('-v', '--verbose', count=True, help='Be more verbose.')
@click.option('-c', '--config', envvar='OPTHUB_EVALUATOR_CONFIG',
              type=click.Path(dir_okay=False), default='opthub-evaluator.yml',
              is_eager=True, callback=load_config, help='Configuration file.')
@click.version_option()
@click.argument('command', envvar='OPTHUB_COMMAND',
              type=str, nargs=-1)
@click.pass_context
def run(ctx, **kwargs):
    """The entrypoint of CLI.

    :param ctx: Click context
    :param kwargs: GraphQL variables
    """

    verbosity = 10 * (kwargs['quiet'] - kwargs['verbose'])
    log_level = logging.WARNING + verbosity
    logging.basicConfig(level=log_level)
    _logger.info('Log level is set to %d', log_level)
    _logger.debug('run(%s)', kwargs)
    transport = RequestsHTTPTransport(
        url=kwargs['url'],
        verify=kwargs['verify'],
        retries=kwargs['retries'],
        headers={'X-Hasura-Admin-Secret': kwargs['apikey']},
    )
    ctx.obj = {
        'client': Client(
            transport=transport,
            fetch_schema_from_transport=True,
        )
    }

    _logger.info('Connect to docker daemon...')
    client = docker.from_env()
    _logger.info('...Connected')

    n_solution = 1
    _logger.info('==================== Solution: %d ====================', n_solution)
    while True:
        try:
            _logger.info('Find solution to evaluate...')
            solution_id = wait_to_fetch(ctx, kwargs['interval'])
            _logger.debug(solution_id)
            _logger.info('...Found')
        except Exception as e:
            if type(e) is InterruptedError:
                _logger.info(e)
                _logger.info('Attempt graceful shutdown...')
                _logger.info('No need to rollback')
                _logger.info('...Shutted down')
                ctx.exit(0)
            else:
                _logger.error(format_exc())
                continue

        try:
            _logger.info('Try to lock solution to evaluate...')
            r = query(ctx, q_start_evaluation, id=solution_id)
            if r['update_solutions']['affected_rows'] == 0:
                _logger.info('...Already locked')
                continue
            elif r['update_solutions']['affected_rows'] != 1:
                _logger.error('Lock error: affected_rows must be 0 or 1, but %s', r)
            solution = r['update_solutions']["returning"][0]
            _logger.info('...Lock aquired')

            _logger.info('Check budget...')
            check_budget(ctx, user_id=solution['owner_id'], match_id=solution['match_id'])
            _logger.info('...OK')

            _logger.info('Parse variable to evaluate...')
            _logger.debug(solution['variable'])
            x = json.dumps(solution['variable']) + '\n'
            _logger.debug(x)
            _logger.info('...Parsed')

            _logger.info('Start container...')
            _logger.debug(solution['match']['problem']['image'])
            c = client.containers.run(
                image=solution['match']['problem']['image'],
                command=kwargs['command'],
                environment={v['key']: v['value']
                    for v in solution['match']['environments']},
                stdin_open=True,
                detach=True,
            )
            _logger.info('...Started: %s', c.name)
 
            _logger.info('Send variable...')
            s = c.attach_socket(params={'stdin': 1, 'stream': 1, 'stdout': 1, 'stderr': 1})
            s._sock.sendall(x.encode('utf-8'))
            _logger.info('...Send')

            _logger.info('Wait for Evaluation...')
            c.wait(timeout=kwargs['timeout'])
            _logger.info('...Evaluated')

            _logger.info('Recieve stdout...')
            stdout = c.logs(stdout=True, stderr=False).decode('utf-8')
            _logger.debug(stdout)
            _logger.info('...Recived')

            if kwargs['rm']:
                _logger.info('Remove container...')
                c.remove()
                _logger.info('...Removed')

            _logger.info('Parse stdout...')
            stdout = json.loads(stdout)
            _logger.debug(stdout)
            _logger.info('...Parsed')

            _logger.info('Check budget...')
            check_budget(ctx, user_id=solution['owner_id'], match_id=solution['match_id'])
            _logger.info('...OK')

            _logger.info('Push evaluation...')
            query(ctx, q_finish_evaluation,
                id=solution['id'],
                objective=stdout.get('objective'),
                constraint=stdout.get('constraint'),
                info=stdout.get('info'),
                error=stdout.get('error'))
            _logger.info('...Pushed')
        except Exception as e:
            if type(e) is InterruptedError:
                _logger.info(e)
                _logger.info('Attempt graceful shutdown...')
                _logger.info('Rollback evaluation...')
                query(ctx, q_cancel_evaluation, id=solution['id'])
                _logger.info('...Rolled back')
                _logger.info('...Shutted down')
                ctx.exit(0)
            _logger.error(format_exc())
            _logger.info('Finish evaluation...')
            query(ctx, q_finish_evaluation,
                id=solution['id'],
                objective=None,
                constraint=None,
                info=None,
                error=str(e))
            _logger.info('...Finished')
            continue

        n_solution += 1
        _logger.info('==================== Solution: %d ====================', n_solution)
