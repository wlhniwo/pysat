"""
Standardized class and functions to test instruments for pysat libraries.  Not
directly called by pytest, but imported as part of test_instruments.py.  Can
be imported directly for external instrument libraries of pysat instruments.
"""
import datetime as dt
from importlib import import_module
import os
import tempfile
import warnings

import pytest

import pysat

# dict, keyed by pysat instrument, with a list of usernames and passwords
user_download_dict = {'supermag_magnetometer': {'user': 'rstoneback',
                                                'password': 'None'}}


def remove_files(inst):
    """Remove any files downloaded as part of the unit tests.

    Parameters
    ----------
    inst : pysat.Instrument
        The instrument object that is being tested

    """
    temp_dir = inst.files.data_path
    # Check if there are less than 20 files to ensure this is the testing
    # directory
    if len(inst.files.files.values) < 20:
        for the_file in list(inst.files.files.values):
            # Check if filename is appended with date for fake_daily data
            # ie, does an underscore exist to the right of the file extension?
            if the_file.rfind('_') > the_file.rfind('.'):
                # If so, trim the appendix to get the original filename
                the_file = the_file[:the_file.rfind('_')]
            file_path = os.path.join(temp_dir, the_file)
            if os.path.isfile(file_path):
                os.unlink(file_path)
    else:
        warnings.warn(''.join(('Files > 20.  Not deleted.  Please check to ',
                               'ensure temp directory is used')))


def generate_instrument_list(inst_loc):
    """Iterate through and create all of the test Instruments needed.


    Parameters
    ----------
    inst_loc : python subpackage
        The location of the instrument subpackage to test,
        eg, 'pysat.instruments'

    Note
    ----
    - Only want to do this once per instrument subpackage being tested.
    - There are a number of checks here to skip import issues for certain cases.
      These are caught later in the tests below as part of InstTestClass. This
      is done to ensure the success of this routine so that tests for all
      instruments can be run uninterupted even if one instrument is broken.

    """

    instrument_names = inst_loc.__all__
    instrument_download = []
    instrument_no_download = []

    # create temporary directory
    dir_name = tempfile.mkdtemp()
    saved_path = pysat.data_dir
    pysat.utils.set_data_dir(dir_name, store=False)

    # Look through list of available instrument modules in the given location
    for inst_module in instrument_names:
        try:
            module = import_module(''.join(('.', inst_module)),
                                   package=inst_loc.__name__)
        except ImportError:
            # If this can't be imported, we can't pull out the info for the
            # download / no_download tests.  Leaving in basic tests for all
            # instruments, but skipping the rest.  The import error will be
            # caught as part of the pytest.mark.all_inst tests in InstTestClass
            pass
        else:
            # try to grab basic information about the module so we
            # can iterate over all of the options
            try:
                info = module._test_dates
            except AttributeError:
                # If a module does not have a test date, add it anyway for
                # other tests.  This will be caught later by
                # InstTestClass.test_instrument_test_dates
                info = {}
                info[''] = {'': dt.datetime(2009, 1, 1)}
                module._test_dates = info
            for sat_id in info.keys():
                for tag in info[sat_id].keys():
                    inst_dict = {'inst_module': module, 'tag': tag,
                                 'sat_id': sat_id}
                    # Initialize instrument so that pysat can generate skip
                    # flags where appropriate
                    inst = pysat.Instrument(inst_module=module,
                                            tag=tag,
                                            sat_id=sat_id,
                                            temporary_file_list=True)
                    travis_skip = ((os.environ.get('TRAVIS') == 'true')
                                   and not inst._test_download_travis)
                    if inst._test_download:
                        if not travis_skip:
                            instrument_download.append(inst_dict)
                    elif not inst._password_req:
                        # we don't want to test download for this combo
                        # But we do want to test the download warnings
                        # for instruments without a password requirement
                        instrument_no_download.append(inst_dict)
    pysat.utils.set_data_dir(saved_path, store=False)

    output = {'names': instrument_names,
              'download': instrument_download,
              'no_download': instrument_no_download}

    return output


def initialize_test_inst_and_date(inst_dict):
    """Initializes the instrument object to test and date

    Paramters
    ---------
    inst_dict : dict
        Dictionary containing specific instrument info, generated by
        generate_instrument_list

    Returns
    -------
    test_inst : pysat.Instrument
        instrument object to be tested
    date : dt.datetime
        test date from module

    """

    test_inst = pysat.Instrument(inst_module=inst_dict['inst_module'],
                                 tag=inst_dict['tag'],
                                 sat_id=inst_dict['sat_id'])
    test_dates = inst_dict['inst_module']._test_dates
    date = test_dates[inst_dict['sat_id']][inst_dict['tag']]
    return test_inst, date


class InstTestClass():
    """Provides standardized tests for pysat instrument libraries.

    Note: Not diretly run by pytest, but inherited through test_instruments.py
    """
    module_attrs = ['platform', 'name', 'tags', 'sat_ids',
                    'load', 'list_files', 'download']
    inst_attrs = ['tag', 'sat_id', 'acknowledgements', 'references']
    inst_callable = ['load', 'list_files', 'download', 'clean', 'default']
    attr_types = {'platform': str, 'name': str, 'tags': dict,
                  'sat_ids': dict, 'tag': str, 'sat_id': str,
                  'acknowledgements': str, 'references': str}

    @pytest.mark.all_inst
    def test_modules_standard(self, inst_name):
        """Checks that modules are importable and have standard properties.
        """
        # ensure that each module is at minimum importable
        module = import_module(''.join(('.', inst_name)),
                               package=self.inst_loc.__name__)
        # Check for presence of basic instrument module attributes
        for mattr in self.module_attrs:
            assert hasattr(module, mattr)
            if mattr in self.attr_types.keys():
                assert isinstance(getattr(module, mattr),
                                  self.attr_types[mattr])

        # Check for presence of required instrument attributes
        for sat_id in module.sat_ids.keys():
            for tag in module.sat_ids[sat_id]:
                inst = pysat.Instrument(inst_module=module, tag=tag,
                                        sat_id=sat_id)

                # Test to see that the class parameters were passed in
                assert isinstance(inst, pysat.Instrument)
                assert inst.platform == module.platform
                assert inst.name == module.name
                assert inst.sat_id == sat_id
                assert inst.tag == tag

                # Test the required class attributes
                for iattr in self.inst_attrs:
                    assert hasattr(inst, iattr)
                    assert isinstance(getattr(inst, iattr),
                                      self.attr_types[iattr])

    @pytest.mark.all_inst
    def test_standard_function_presence(self, inst_name):
        """Check if each function is callable and all required functions exist
        """
        module = import_module(''.join(('.', inst_name)),
                               package=self.inst_loc.__name__)

        # Test for presence of all standard module functions
        for mcall in self.inst_callable:
            if hasattr(module, mcall):
                # If present, must be a callable function
                assert callable(getattr(module, mcall))
            else:
                # If absent, must not be a required function
                assert mcall not in self.module_attrs

    @pytest.mark.all_inst
    def test_instrument_test_dates(self, inst_name):
        """Check that module has structured test dates correctly."""
        module = import_module(''.join(('.', inst_name)),
                               package=self.inst_loc.__name__)
        info = module._test_dates
        for sat_id in info.keys():
            for tag in info[sat_id].keys():
                assert isinstance(info[sat_id][tag], dt.datetime)

    @pytest.mark.first
    @pytest.mark.download
    def test_download(self, inst_dict):
        """Check that instruments are downloadable."""

        test_inst, date = initialize_test_inst_and_date(inst_dict)

        # check for username
        inst_name = '_'.join((test_inst.platform, test_inst.name))
        dl_dict = user_download_dict[inst_name] if inst_name in \
            user_download_dict.keys() else {}
        test_inst.download(date, date, **dl_dict)
        assert len(test_inst.files.files) > 0

    @pytest.mark.second
    @pytest.mark.download
    @pytest.mark.parametrize("clean_level", ['none', 'dirty', 'dusty', 'clean'])
    def test_load(self, clean_level, inst_dict):
        """Check that instruments load at each cleaning level."""

        test_inst, date = initialize_test_inst_and_date(inst_dict)
        if len(test_inst.files.files) > 0:
            # Set Clean Level
            test_inst.clean_level = clean_level
            target = 'Fake Data to be cleared'
            test_inst.data = [target]
            try:
                test_inst.load(date=date)
            except ValueError as verr:
                # Check if instrument is failing due to strict time flag
                if str(verr).find('Loaded data') > 0:
                    test_inst.strict_time_flag = False
                    with warnings.catch_warnings(record=True) as war:
                        test_inst.load(date=date)
                    assert len(war) >= 1
                    categories = [war[j].category for j in range(0, len(war))]
                    assert UserWarning in categories
                else:
                    # If error message does not match, raise error anyway
                    raise(verr)

            # Make sure fake data is cleared
            assert target not in test_inst.data
            # If cleaning not used, something should be in the file
            # Not used for clean levels since cleaning may remove all data
            if clean_level == "none":
                assert not test_inst.empty
            # For last parametrized clean_level, remove files
            if clean_level == "clean":
                remove_files(test_inst)
        else:
            pytest.skip("Download data not available")

    @pytest.mark.download
    def test_remote_file_list(self, inst_dict):
        """Check if optional list_remote_files routine exists and is callable.
        """
        test_inst, date = initialize_test_inst_and_date(inst_dict)
        name = '_'.join((test_inst.platform, test_inst.name))

        if hasattr(getattr(self.inst_loc, name), 'list_remote_files'):
            assert callable(test_inst.remote_file_list)
            files = test_inst.remote_file_list(start=date, stop=date)
            # If test date is correctly chosen, files should exist
            assert len(files) > 0
        else:
            pytest.skip("remote_file_list not available")

    @pytest.mark.no_download
    def test_download_warning(self, inst_dict):
        """Check that instruments without download support have a warning."""
        test_inst, date = initialize_test_inst_and_date(inst_dict)

        with warnings.catch_warnings(record=True) as war:
            test_inst.download(date, date)

        assert len(war) >= 1
        categories = [war[j].category for j in range(0, len(war))]
        assert UserWarning in categories
