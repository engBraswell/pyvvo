# Standard library.
import unittest
from unittest.mock import patch

# pyvvo.
from pyvvo import sparql

# Third-party.
import simplejson as json
# noinspection PyPackageRequirements
from stomp.exception import ConnectFailedException
import pandas as pd
import numpy as np

# Hard-code 8500 node feeder MRID.
FEEDER_MRID = '_4F76A5F9-271D-9EB8-5E31-AA362D86F2C3'

# We'll be mocking some query returns.
MOCK_RETURN = pd.DataFrame({'name': ['thing1', 'thing2'],
                            'prop': ['prop1', 'prop2']})


class SPARQLManagerTestCase(unittest.TestCase):
    """General tests for the SPARQLManager

    NOTE: Tests will be skipped if platform connection fails.

    TODO: Rather than relying on a connection, we should probably mock
        everything up. However, connecting to the platform and actually
        performing queries helps catch regression issues with the
        platform itself, which is handy.
    """

    def setUp(self):
        """Attempt to connect to the platform."""
        try:
            self.sparql = sparql.SPARQLManager(feeder_mrid=FEEDER_MRID)
        except ConnectFailedException:
            # We cannot connect to the platform.
            raise unittest.SkipTest('Failed to connect to GridAPPS-D.')

    def mock_query(self, function_string, query, to_numeric, **kwargs):
        """Helper for mocking a call to _query."""

        with patch('pyvvo.sparql.SPARQLManager._query',
                   return_value=MOCK_RETURN) as mock:
            fn_call = getattr(self.sparql, function_string)
            result = fn_call(**kwargs)
            mock.assert_called_once()
            query_string = getattr(self.sparql, query)
            mock.assert_called_with(
                query_string.format(
                    feeder_mrid=self.sparql.feeder_mrid, **kwargs),
                to_numeric=to_numeric)

        pd.testing.assert_frame_equal(MOCK_RETURN, result)

    @patch('pyvvo.sparql.SPARQLManager._query', return_value=MOCK_RETURN)
    @patch('pyvvo.sparql.map_dataframe_columns', return_value=MOCK_RETURN)
    def mock_query_and_map_dataframe_columns(self, map_df_mock, query_mock,
                                             function_string, query,
                                             to_numeric):
        """Helper for mocking both _query and map_dataframe_columns.

        Functions like query_capacitors and query_regulators call both.
        """
        fn_call = getattr(self.sparql, function_string)
        result = fn_call()
        map_df_mock.assert_called_once()
        query_mock.assert_called_once()

        query_string = getattr(self.sparql, query)
        query_mock.assert_called_with(
            query_string.format(feeder_mrid=self.sparql.feeder_mrid),
            to_numeric=to_numeric)

        pd.testing.assert_frame_equal(result, MOCK_RETURN)

    def test_sparql_manager_is_sparql_manager(self):
        self.assertIsInstance(self.sparql, sparql.SPARQLManager)

    def test_sparql_manager_bindings_to_dataframe(self):
        bindings = [
            {'name': {'type': 'literal', 'value': 'obj1'},
             'stuff': {'value': '2'}
             },
            {'name': {'type': 2, 'value': 17},
             'stuff': {'value': 'I am a thing.'}
             }
        ]

        expected = pd.DataFrame(
            {
                'name': ['obj1', 17],
                'stuff': ['2', 'I am a thing.']
            }
        )

        # Ensure _check_bindings is called.
        with patch('pyvvo.sparql.SPARQLManager._check_bindings',
                   return_value=None) as mock:
            # Check the return value.
            actual = self.sparql._bindings_to_dataframe(bindings,
                                                        to_numeric=False)

            mock.assert_called_once()

        pd.testing.assert_frame_equal(expected, actual)

    def test_sparql_manager_bindings_to_dataframe_mismatched_lengths(self):
        """A warning should be thrown, output should have NaNs."""
        bindings = [
            {'name': {'type': 'literal', 'value': 'obj1'},
             'things': {'value': '2'}
             },
            {'name': {'type': 2, 'value': 17},
             'stuff': {'value': 'I am a thing.'},
             'things': {'value': '11'}
             }
        ]

        expected = pd.DataFrame(
            {
                'name': ['obj1', 17],
                'stuff': [np.nan, 'I am a thing.'],
                'things': ['2', '11']
            }
        )

        # Ensure a warning is logged.
        with self.assertLogs(self.sparql.log, level='WARN'):
            actual = self.sparql._bindings_to_dataframe(bindings,
                                                        to_numeric=False)

        # Ensure values match.
        pd.testing.assert_frame_equal(actual, expected)

    def test_sparql_manager_bindings_to_dataframe_no_value(self):
        self.assertRaises(KeyError, self.sparql._bindings_to_dataframe,
                          bindings=[{'name': {'type': 'literal'}}],
                          to_numeric=False)

    def test_sparql_manager_check_bindings_bad_binding_type(self):
        self.assertRaises(TypeError, self.sparql._check_bindings,
                          bindings={'name': {'value': 'device',
                                             'type': 'stuff'}})

    @unittest.expectedFailure
    def test_sparql_manager_check_bindings_bad_second_element(self):
        """Our test is primitive and only checks the first element."""
        self.assertRaises(TypeError, self.sparql._check_bindings,
                          bindings=[{'name': {'value': 'hi'}},
                                    'Not a dict.'])

    def test_sparql_manager_bindings_to_dataframe_bad_binding_element(self):
        self.assertRaises(TypeError, self.sparql._bindings_to_dataframe,
                          bindings=[{'name': 10}])

    def test_sparql_manager_query_simple_query(self):
        """Hard-coded MRID for 8500 node capacitor."""
        query = (self.sparql.PREFIX +
                 "SELECT ?name "
                 "WHERE { "
                 '?s c:IdentifiedObject.mRID'
                 '  "_A5866105-A527-F682-C982-69807C0E088B". '
                 "?s c:IdentifiedObject.name ?name. "
                 "} "
                 "ORDER BY ?name "
                 )

        actual = self.sparql._query(query, to_numeric=False)
        expected = pd.DataFrame({'name': ['capbank0a']})
        pd.testing.assert_frame_equal(actual, expected)

    def test_sparql_manager_query_calls_query_platform(self):
        """Ensure _query_named_objects calls _query_platform, as
        _query_platform does the error handling.
        """
        # Mock the silly-deep return from the platform.
        config = \
            {'return_value':
                {'data':
                    {'results':
                        {'bindings':
                            [{'name': {
                                'value': 'object1'}}]}}}}

        with patch('pyvvo.sparql.SPARQLManager._query_platform', **config) \
                as mock:
            actual = self.sparql._query('some query', to_numeric=False)
            mock.assert_called_once()
            mock.assert_called_with('some query')

        # Test return value.
        expected = pd.DataFrame({'name': ['object1']})
        pd.testing.assert_frame_equal(actual, expected)

    def test_sparql_manager_query_platform_no_results(self):
        """Give a SPARQL query which won't return any data."""
        query = (self.sparql.PREFIX +
                 "SELECT ?name "
                 "WHERE { "
                 '?s c:NotReal ?name. '
                 "} "
                 "ORDER BY ?name "
                 )

        self.assertRaises(sparql.SPARQLQueryReturnEmptyError,
                          self.sparql._query_platform, query_string=query)

    def test_sparql_manager_query_platform_bad_syntax(self):
        """Give SPARQL query with bad syntax."""
        query = 'This is not actually a query.'
        self.assertRaises(sparql.SPARQLQueryError, self.sparql._query_platform,
                          query_string=query)

    def test_sparql_manager_query_capacitors_expected_return(self):
        """Ensure we get the expected return."""
        actual = self.sparql.query_capacitors()

        # Uncomment to recreate expected output.
        # actual.to_csv('query_capacitors.csv', index=False)

        # Compare results
        expected = pd.read_csv('query_capacitors.csv')
        pd.testing.assert_frame_equal(actual, expected)

    def test_sparql_manager_query_capacitors_calls_query_and_map(self):
        """query_capacitors must call _query and map_dataframe_columns.
        """

        self.mock_query_and_map_dataframe_columns(
            function_string='query_capacitors',
            query='CAPACITOR_QUERY', to_numeric=True)

    def test_sparql_manager_query_regulators_expected_return(self):
        """Ensure we get the expected return."""
        actual = self.sparql.query_regulators()

        # Uncomment to recreated expected output.
        # actual.to_csv('query_regulators.csv', index=False)

        expected = pd.read_csv('query_regulators.csv')

        pd.testing.assert_frame_equal(actual, expected)

    def test_sparql_manager_query_regulators_calls_query(self):
        """query_regulators must call _query."""
        self.mock_query_and_map_dataframe_columns(
            function_string='query_regulators',
            query='REGULATOR_QUERY', to_numeric=True)

    def test_sparql_manager_query_load_nominal_voltage_calls_query(self):
        """query_load_nominal_voltage must call _query."""

        self.mock_query(
            function_string='query_load_nominal_voltage',
            query='LOAD_NOMINAL_VOLTAGE_QUERY', to_numeric=True)

    def test_sparql_manager_query_load_nominal_voltage_expected_return(self):
        """Check one of the elements from query_load_nominal_voltage."""
        expected = pd.Series({'name': '2127146b0', 'bus': 'sx3160864b',
                              'basev': 208, 'conn': 'Y', 'phases': 's1,s2'})

        full_actual = self.sparql.query_load_nominal_voltage()

        self.assertIn(expected['name'], full_actual['name'].values)

        actual = full_actual[full_actual['name'] == '2127146b0'].iloc[0]

        pd.testing.assert_series_equal(actual.sort_index(),
                                       expected.sort_index(),
                                       check_names=False)

    def test_sparql_manager_query_load_measurements_calls_query(self):
        """query_load_measurements must call _query."""
        self.mock_query(
            function_string='query_load_measurements',
            query='LOAD_MEASUREMENTS_QUERY', to_numeric=False)

    def test_sparql_manager_query_load_measurements_expected_return(self):
        """Check one of the elements from query_load_measurements."""

        full_actual = self.sparql.query_load_measurements()

        actual = full_actual[full_actual['load'] == '21395720c0']

        # Uncomment to recreate expected.
        # actual.to_csv('query_load_measurements.csv', index=True)

        expected = pd.read_csv('query_load_measurements.csv', index_col=0)

        pd.testing.assert_frame_equal(actual, expected)

    def test_sparql_manager_query_all_measurements_calls_query(self):
        """Ensure query_all_measurements calls _query."""
        self.mock_query(function_string='query_all_measurements',
                        query='ALL_MEASUREMENTS_QUERY', to_numeric=False)

    def test_sparql_manager_query_rtc_measurements_calls_query(self):
        """Ensure query_rtc_measurements calls _query"""
        self.mock_query(function_string='query_rtc_measurements',
                        query='RTC_POSITION_MEASUREMENT_QUERY',
                        to_numeric=False)

    def test_sparql_manager_query_rtc_measurements_4_regs(self):
        """The 8500 node system has 4 regulators, all with measurements.

        Ensure performing the actual query returns 4 named objects, and
        that each of the named objects has 3 measurements.
        """
        rtc_meas = self.sparql.query_rtc_measurements()

        # Ensure we get measurements associated with four regulators.
        regs = rtc_meas['eqname'].unique()
        self.assertEqual(4, len(regs))

        # For each of the four elements, ensure we have 3 measurements.
        for reg in regs:
            meas = rtc_meas[rtc_meas['eqname'] == reg]
            self.assertEqual(3, meas.shape[0])

    def test_sparql_manager_query_capacitor_measurements_calls_query(self):
        """Ensure query_capacitor_measurements calls _query"""
        self.mock_query(
            function_string='query_capacitor_measurements',
            query='CAPACITOR_STATUS_MEASUREMENT_QUERY', to_numeric=False)

    def test_sparql_manager_query_substation_source_calls_query(self):
        """Ensure query_capacitor_measurements calls _query"""
        self.mock_query(
            function_string='query_substation_source',
            query='SUBSTATION_SOURCE_QUERY', to_numeric=True)

    def test_sparql_manager_query_substation_source_expected_return(self):
        """Test return is as expected."""
        actual = self.sparql.query_substation_source()

        # Uncomment to regenerate expected return.
        # actual.to_csv('query_substation_source.csv')

        expected = pd.read_csv('query_substation_source.csv', index_col=0)

        pd.testing.assert_frame_equal(actual, expected)

    def test_sparql_manager_query_measurements_for_bus_calls_query(self):
        # NOTE: bus_mrid is for the substation source bus.
        self.mock_query(
            function_string='query_measurements_for_bus',
            query='MEASUREMENTS_FOR_BUS_QUERY',
            bus_mrid='_E555E153-3529-7B82-1649-B015B154BFA6',
            to_numeric=False
        )

    def test_sparql_manager_query_measurements_for_bus_expected_return(self):
        # NOTE: bus_mrid is for the substation source bus.
        actual = self.sparql.query_measurements_for_bus(
            bus_mrid='_E555E153-3529-7B82-1649-B015B154BFA6')

        # Uncomment to recreate expected value.
        # actual.to_csv('query_measurements_for_bus.csv')

        expected = pd.read_csv('query_measurements_for_bus.csv', index_col=0)

        pd.testing.assert_frame_equal(actual, expected)


if __name__ == '__main__':
    unittest.main()