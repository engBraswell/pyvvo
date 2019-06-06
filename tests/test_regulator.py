import unittest
from unittest.mock import patch
import pyvvo.equipment.regulator as regulator
from copy import copy, deepcopy
import os
import pandas as pd

# Handle pathing.
THIS_DIR = os.path.dirname(os.path.abspath(__file__))
REGULATORS = os.path.join(THIS_DIR, 'query_regulators.csv')


class InitializeControllableRegulatorsTestCase(unittest.TestCase):
    """Test initialize_controllable_regulators"""
    @classmethod
    def setUpClass(cls):
        cls.df = pd.read_csv(REGULATORS)
        cls.regs = regulator.initialize_controllable_regulators(cls.df)

    def test_four_regs(self):
        """There should be 4 three phase regulators"""
        self.assertEqual(len(self.regs), 4)

    def test_all_regs(self):
        """Every item should be a RegulatorMultiPhase"""
        for key, reg in self.regs.items():
            with self.subTest('reg = {}'.format(reg)):
                self.assertIsInstance(reg, regulator.RegulatorMultiPhase)

    def test_ltc_filter(self):
        """If a regulator's ltc_flag is false, it shouldn't be included.
        """
        # Get a copy of the DataFrame.
        df = self.df.copy(deep=True)

        # Set the first three ltc_flags to False.
        # NOTE: This is hard-coding based on the DataFrame have regs in
        # order.
        df.loc[0:2, 'ltc_flag'] = False

        # Create regulators. NOTE: This should log.
        with self.assertLogs(regulator.LOG, 'INFO'):
            regs = regulator.initialize_controllable_regulators(df)

        # There should be three now instead of four.
        self.assertEqual(len(regs), 3)


class TapCIMToGLDTestCase(unittest.TestCase):
    """NOTE: The way the platform currently handles 'step' is likely
    wrong. Test this after there's a way forward identified.
    """

    def test_tap_cim_to_gld_1(self):
        actual = regulator._tap_cim_to_gld(step=16, neutral_step=16)
        self.assertEqual(0, actual)

    def test_tap_cim_to_gld_2(self):
        actual = regulator._tap_cim_to_gld(step=1, neutral_step=8)
        self.assertEqual(-7, actual)

    def test_tap_cim_to_gld_3(self):
        actual = regulator._tap_cim_to_gld(step=24, neutral_step=16)
        self.assertEqual(8, actual)

    def test_tap_cim_to_gld_4(self):
        actual = regulator._tap_cim_to_gld(step=0, neutral_step=16)
        self.assertEqual(-16, actual)


class TapGLDToCIMTestCase(unittest.TestCase):

    def test_tap_gld_to_cim_1(self):
        actual = regulator._tap_gld_to_cim(tap_pos=2, neutral_step=8)
        self.assertEqual(10, actual)

    def test_tap_gld_to_cim_2(self):
        actual = regulator._tap_gld_to_cim(tap_pos=-10, neutral_step=16)

        self.assertEqual(6, actual)

    def test_tap_gld_to_cim_3(self):
        actual = regulator._tap_gld_to_cim(tap_pos=0, neutral_step=10)
        self.assertEqual(10, actual)


class RegulatorMultiPhaseInitializationTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        # Set up some default inputs to RegulatorSinglePhase.
        cls.inputs = \
            {'control_mode': 'voltage',
             'enabled': True, 'high_step': 32, 'low_step': 0,
             'mrid': '_3E73AD1D-08AF-A34B-33D2-1FCE3533380A',
             'name': 'FEEDER_REG', 'neutral_step': 16, 'phase': 'A',
             'tap_changer_mrid': '_330E7EDE-2C70-8F72-B183-AA4BA3C5E221',
             'step': 18, 'step_voltage_increment': 0.625}

    def test_bad_input_type(self):
        self.assertRaises(TypeError, regulator.RegulatorMultiPhase,
                          'hello')

    def test_bad_input_list_length_1(self):
        with self.assertRaisesRegex(ValueError,
                                    r'1 <= len\(regulator_list\) <= 3'):
            regulator.RegulatorMultiPhase([])

    def test_bad_input_list_length_2(self):
        with self.assertRaisesRegex(ValueError,
                                    r'1 <= len\(regulator_list\) <= 3'):
            regulator.RegulatorMultiPhase([1, 2, 3, 4])

    def test_bad_input_list_type(self):
        self.assertRaises(TypeError, regulator.RegulatorMultiPhase,
                          (1, 2, 3))

    def test_successful_init_1(self):
        """Pass three single phase regs."""
        input1 = self.inputs
        input2 = copy(self.inputs)
        input3 = copy(self.inputs)
        input2['phase'] = 'b'
        input3['phase'] = 'C'

        reg1 = regulator.RegulatorSinglePhase(**input1)
        reg2 = regulator.RegulatorSinglePhase(**input2)
        reg3 = regulator.RegulatorSinglePhase(**input3)

        reg_multi_phase = regulator.RegulatorMultiPhase((reg1, reg2, reg3))

        self.assertEqual(reg_multi_phase.name, self.inputs['name'])
        self.assertEqual(reg_multi_phase.mrid, self.inputs['mrid'])
        self.assertIs(reg_multi_phase.a, reg1)
        self.assertIs(reg_multi_phase.b, reg2)
        self.assertIs(reg_multi_phase.c, reg3)

    def test_successful_init_2(self):
        """Pass two single phase regs."""
        input1 = self.inputs
        input3 = copy(self.inputs)
        input3['phase'] = 'C'

        reg1 = regulator.RegulatorSinglePhase(**input1)
        reg3 = regulator.RegulatorSinglePhase(**input3)

        reg_multi_phase = regulator.RegulatorMultiPhase((reg1, reg3))

        # noinspection SpellCheckingInspection
        self.assertEqual(reg_multi_phase.name, self.inputs['name'])
        self.assertEqual(reg_multi_phase.mrid, self.inputs['mrid'])
        self.assertIs(reg_multi_phase.a, reg1)
        self.assertIs(reg_multi_phase.c, reg3)

    def test_successful_init_3(self):
        """Pass a single mocked single phase regs."""
        reg1 = regulator.RegulatorSinglePhase(**self.inputs)

        reg_multi_phase = regulator.RegulatorMultiPhase((reg1, ))

        # noinspection SpellCheckingInspection
        self.assertEqual(reg_multi_phase.name, self.inputs['name'])
        self.assertEqual(reg_multi_phase.mrid, self.inputs['mrid'])
        self.assertIs(reg_multi_phase.a, reg1)

    def test_mismatched_names(self):
        """All single phase regs should have the same name."""
        input1 = self.inputs
        input2 = copy(self.inputs)
        input3 = copy(self.inputs)
        input2['phase'] = 'b'
        input2['name'] = 'just kidding'
        input3['phase'] = 'C'
        reg1 = regulator.RegulatorSinglePhase(**input1)
        reg2 = regulator.RegulatorSinglePhase(**input2)
        reg3 = regulator.RegulatorSinglePhase(**input3)

        with self.assertRaisesRegex(ValueError, 'matching "name" attributes'):
            regulator.RegulatorMultiPhase((reg1, reg2, reg3))

    def test_mismatched_mrids(self):
        """All single phase regs should have the same name."""
        input1 = self.inputs
        input2 = copy(self.inputs)
        input3 = copy(self.inputs)
        input2['phase'] = 'b'
        input2['mrid'] = 'whoops'
        input3['phase'] = 'C'
        reg1 = regulator.RegulatorSinglePhase(**input1)
        reg2 = regulator.RegulatorSinglePhase(**input2)
        reg3 = regulator.RegulatorSinglePhase(**input3)

        with self.assertRaisesRegex(ValueError, 'matching "mrid" attributes'):
            regulator.RegulatorMultiPhase((reg1, reg2, reg3))

    def test_multiple_same_phases(self):
        """Passing multiple RegulatorSinglePhase objects on the same phase
        is not allowed.
        """
        input1 = self.inputs
        input2 = copy(self.inputs)
        input3 = copy(self.inputs)
        input3['phase'] = 'C'
        reg1 = regulator.RegulatorSinglePhase(**input1)
        reg2 = regulator.RegulatorSinglePhase(**input2)
        reg3 = regulator.RegulatorSinglePhase(**input3)

        with self.assertRaisesRegex(ValueError,
                                    'Multiple regulators for phase'):
            regulator.RegulatorMultiPhase((reg1, reg2, reg3))


class RegulatorSinglePhaseInitializationTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.inputs = \
            {'control_mode': 'voltage',
             'enabled': True, 'high_step': 32, 'low_step': 0,
             'mrid': '_3E73AD1D-08AF-A34B-33D2-1FCE3533380A',
             'name': 'FEEDER_REG', 'neutral_step': 16, 'phase': 'A',
             'tap_changer_mrid': '_330E7EDE-2C70-8F72-B183-AA4BA3C5E221',
             'step': 18, 'step_voltage_increment': 0.625}

        cls.reg = regulator.RegulatorSinglePhase(**cls.inputs)

    def test_attributes(self):
        """The inputs should match the attributes."""
        for key, value in self.inputs.items():
            with self.subTest('attribute: {}'.format(key)):
                self.assertEqual(getattr(self.reg, key), value)

    def test_raise_taps(self):
        self.assertEqual(self.reg.raise_taps, 16)

    def test_lower_taps(self):
        self.assertEqual(self.reg.lower_taps, 16)

    def test_tap_pos(self):
        self.assertEqual(self.reg.tap_pos, 2)

    def test_update_step(self):
        reg = regulator.RegulatorSinglePhase(**self.inputs)

        self.assertEqual(reg.step, 18)
        self.assertEqual(reg.tap_pos, 2)

        reg.step = 15
        self.assertEqual(reg.step, 15)
        self.assertEqual(reg.tap_pos, -1)

    def test_update_tap_pos(self):
        reg = regulator.RegulatorSinglePhase(**self.inputs)

        self.assertEqual(reg.step, 18)
        self.assertEqual(reg.tap_pos, 2)

        reg.tap_pos = -15
        self.assertEqual(reg.step, 1)
        self.assertEqual(reg.tap_pos, -15)


class RegulatorSinglePhaseBadInputsTestCase(unittest.TestCase):

    @classmethod
    def setUpClass(cls):
        cls.inputs = \
            {'control_mode': 'voltage',
             'enabled': True, 'high_step': 32, 'low_step': 0,
             'mrid': '_3E73AD1D-08AF-A34B-33D2-1FCE3533380A',
             'name': 'FEEDER_REG', 'neutral_step': 16, 'phase': 'A',
             'tap_changer_mrid': '_330E7EDE-2C70-8F72-B183-AA4BA3C5E221',
             'step': 1.0125, 'step_voltage_increment': 0.625}

    def test_bad_mrid_type(self):
        i = deepcopy(self.inputs)
        i['mrid'] = 10
        self.assertRaises(TypeError, regulator.RegulatorSinglePhase, **i)

    def test_bad_name_type(self):
        i = deepcopy(self.inputs)
        i['name'] = {'name': 'reg'}
        self.assertRaises(TypeError, regulator.RegulatorSinglePhase, **i)

    def test_bad_phase_type(self):
        i = deepcopy(self.inputs)
        i['name'] = ['name', 'yo']
        self.assertRaises(TypeError, regulator.RegulatorSinglePhase, **i)

    def test_bad_phase_value(self):
        i = deepcopy(self.inputs)
        i['phase'] = 'N'
        self.assertRaises(ValueError, regulator.RegulatorSinglePhase, **i)

    def test_bad_tap_changer_mrid_type(self):
        i = deepcopy(self.inputs)
        i['tap_changer_mrid'] = 111
        self.assertRaises(TypeError, regulator.RegulatorSinglePhase, **i)

    def test_bad_step_voltage_increment_type(self):
        i = deepcopy(self.inputs)
        i['step_voltage_increment'] = 1
        self.assertRaises(TypeError, regulator.RegulatorSinglePhase, **i)

    def test_bad_control_mode_type(self):
        i = deepcopy(self.inputs)
        i['control_mode'] = (0, 0, 1)
        self.assertRaises(TypeError, regulator.RegulatorSinglePhase, **i)

    def test_bad_control_mode_value(self):
        i = deepcopy(self.inputs)
        i['control_mode'] = 'my mode'
        self.assertRaises(ValueError, regulator.RegulatorSinglePhase, **i)

    def test_bad_enabled_type(self):
        i = deepcopy(self.inputs)
        i['enabled'] = 'true'
        self.assertRaises(TypeError, regulator.RegulatorSinglePhase, **i)

    def test_bad_high_step_type(self):
        i = deepcopy(self.inputs)
        i['high_step'] = 10.1
        self.assertRaises(TypeError, regulator.RegulatorSinglePhase, **i)

    def test_bad_low_step_type(self):
        i = deepcopy(self.inputs)
        i['low_step'] = 10+1j
        self.assertRaises(TypeError, regulator.RegulatorSinglePhase, **i)

    def test_bad_neutral_step_type(self):
        i = deepcopy(self.inputs)
        i['neutral_step'] = '16'
        self.assertRaises(TypeError, regulator.RegulatorSinglePhase, **i)

    def test_bad_step_values_1(self):
        i = deepcopy(self.inputs)
        i['low_step'] = 17
        i['neutral_step'] = 16
        i['high_step'] = 20
        self.assertRaises(ValueError, regulator.RegulatorSinglePhase, **i)

    def test_bad_step_values_2(self):
        i = deepcopy(self.inputs)
        i['low_step'] = 0
        i['neutral_step'] = 21
        i['high_step'] = 20
        self.assertRaises(ValueError, regulator.RegulatorSinglePhase, **i)

    def test_bad_step_values_3(self):
        i = deepcopy(self.inputs)
        i['low_step'] = 0
        i['neutral_step'] = 0
        i['high_step'] = -1
        self.assertRaises(ValueError, regulator.RegulatorSinglePhase, **i)

    def test_bad_step_type(self):
        # TODO: Update when platform is updated.
        i = deepcopy(self.inputs)
        i['step'] = 2.0
        self.assertRaises(TypeError, regulator.RegulatorSinglePhase, **i)


if __name__ == '__main__':
    unittest.main()
