"""test_se_lock.py module."""

########################################################################
# Standard Library
########################################################################
from dataclasses import dataclass
from enum import Enum, auto
import itertools as it
import logging
import re
import threading
import time
from typing import Optional

########################################################################
# Third Party
########################################################################
from scottbrian_utils.flower_box import print_flower_box_msg as flowers
from scottbrian_utils.log_verifier import LogVer
from scottbrian_utils.msgs import Msgs
from scottbrian_utils.stop_watch import StopWatch
import pytest

########################################################################
# Local
########################################################################
from scottbrian_locking.se_lock import (
    SELock,
    SELockShare,
    SELockExcl,
    SELockObtain,
    LockItem,
)
from scottbrian_locking.se_lock import (
    AttemptedReleaseByExclusiveWaiter,
    AttemptedReleaseBySharedWaiter,
    AttemptedReleaseOfUnownedLock,
    LockVerifyError,
    SELockInputError,
    SELockAlreadyOwnedError,
    SELockObtainTimeout,
    SELockOwnerNotAlive,
    SELockObtainMode,
)

########################################################################
# Set up logging
########################################################################
logger = logging.getLogger(__name__)
logger.debug("about to start the tests")


########################################################################
# SELock test exceptions
########################################################################
class ErrorTstSELock(Exception):
    """Base class for exception in this module."""

    pass


class BadRequestStyleArg(ErrorTstSELock):
    """BadRequestStyleArg exception class."""

    pass


class InvalidRouteNum(ErrorTstSELock):
    """InvalidRouteNum exception class."""

    pass


class InvalidRequestType(ErrorTstSELock):
    """The request is not valid."""

    pass


class InvalidModeNum(ErrorTstSELock):
    """InvalidModeNum exception class."""

    pass


########################################################################
# ContextArg
########################################################################
class ContextArg(Enum):
    """ContextArg used to select which for of obtain lock to use."""

    NoContext = auto()
    ContextExclShare = auto()
    ContextObtain = auto()


########################################################################
# TimeoutType
########################################################################
class TimeoutType(Enum):
    TimeoutNone = auto()
    TimeoutFalse = auto()
    TimeoutTrue = auto()


lock_request_list = (
    SELock.ReqType.Exclusive,
    SELock.ReqType.ExclusiveRecursive,
    SELock.ReqType.Share,
    SELock.ReqType.Release,
)


########################################################################
# TestSELockBasic class to test SELock methods
########################################################################
class TestSELockErrors:
    """TestSELock class."""

    ####################################################################
    # test_lock_verify_bad_input
    ####################################################################
    def test_lock_verify_bad_input(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test lock_verify with bad input."""
        ################################################################
        # SELockInputError
        ################################################################
        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_locking.se_lock")

        ml_call_seq = (
            "Request call sequence: python.py::pytest_pyfunc_call:[0-9]+ -> "
            "test_se_lock.py::TestSELockErrors.test_lock_verify_bad_input:[0-9]+"
        )

        a_lock = SELock()

        ml_error_msg = (
            "lock_verify raising SELockInputError. Nothing was requested to "
            "be verified with exp_q=None and verify_structures=False. "
        ) + ml_call_seq

        log_ver.add_pattern(pattern=ml_error_msg, level=logging.ERROR)
        with pytest.raises(SELockInputError, match=ml_error_msg):
            a_lock.verify_lock(verify_structures=False)

        log_ver.add_pattern(pattern=ml_error_msg, level=logging.ERROR)
        with pytest.raises(SELockInputError, match=ml_error_msg):
            a_lock.verify_lock(exp_q=None, verify_structures=False)

        ml_error_msg = (
            "lock_verify raising SELockInputError. exp_q must be "
            "specified if any of exp_owner_count, exp_excl_wait_count, or "
            "timeout is specified. exp_q=None, exp_owner_count=0, "
            "exp_excl_wait_count=None, timeout=None. "
        ) + ml_call_seq

        log_ver.add_pattern(pattern=ml_error_msg, level=logging.ERROR)
        with pytest.raises(SELockInputError, match=ml_error_msg):
            a_lock.verify_lock(exp_owner_count=0)

        ml_error_msg = (
            "lock_verify raising SELockInputError. exp_q must be "
            "specified if any of exp_owner_count, exp_excl_wait_count, or "
            "timeout is specified. exp_q=None, exp_owner_count=None, "
            "exp_excl_wait_count=0, timeout=None. "
        ) + ml_call_seq

        log_ver.add_pattern(pattern=ml_error_msg, level=logging.ERROR)
        with pytest.raises(SELockInputError, match=ml_error_msg):
            a_lock.verify_lock(exp_excl_wait_count=0)

        ml_error_msg = (
            "lock_verify raising SELockInputError. exp_q must be "
            "specified if any of exp_owner_count, exp_excl_wait_count, or "
            "timeout is specified. exp_q=None, exp_owner_count=None, "
            "exp_excl_wait_count=None, timeout=0. "
        ) + ml_call_seq

        log_ver.add_pattern(pattern=ml_error_msg, level=logging.ERROR)
        with pytest.raises(SELockInputError, match=ml_error_msg):
            a_lock.verify_lock(timeout=0)

        for exp_owner_count in (None, 0):
            for exp_excl_wait_count in (None, 0):
                for timeout in (None, 0):
                    ml_error_msg = (
                        "lock_verify raising SELockInputError. exp_q must be "
                        "specified if any of exp_owner_count, exp_excl_wait_count, or "
                        f"timeout is specified. exp_q=None, {exp_owner_count=}, "
                        f"{exp_excl_wait_count=}, {timeout=}. "
                    ) + ml_call_seq
                    if not (
                        exp_owner_count is None
                        and exp_excl_wait_count is None
                        and timeout is None
                    ):
                        log_ver.add_pattern(pattern=ml_error_msg, level=logging.ERROR)
                        with pytest.raises(SELockInputError, match=ml_error_msg):
                            a_lock.verify_lock(
                                exp_owner_count=exp_owner_count,
                                exp_excl_wait_count=exp_excl_wait_count,
                                timeout=timeout,
                            )

                        log_ver.add_pattern(pattern=ml_error_msg, level=logging.ERROR)
                        with pytest.raises(SELockInputError, match=ml_error_msg):
                            a_lock.verify_lock(
                                exp_owner_count=exp_owner_count,
                                exp_excl_wait_count=exp_excl_wait_count,
                                timeout=timeout,
                                verify_structures=True,
                            )

                        ml_error_msg = (
                            "lock_verify raising SELockInputError. Nothing was "
                            "requested to be verified with exp_q=None and "
                            "verify_structures=False. "
                        ) + ml_call_seq

                        log_ver.add_pattern(pattern=ml_error_msg, level=logging.ERROR)
                        with pytest.raises(SELockInputError, match=ml_error_msg):
                            a_lock.verify_lock(
                                exp_owner_count=exp_owner_count,
                                exp_excl_wait_count=exp_excl_wait_count,
                                timeout=timeout,
                                verify_structures=False,
                            )

        ################################################################
        # all other combinations should not produce an error
        ################################################################

        a_lock.verify_lock()
        a_lock.verify_lock(exp_q=[])
        a_lock.verify_lock(exp_q=[], verify_structures=False)
        a_lock.verify_lock(verify_structures=True)
        a_lock.verify_lock(exp_q=[], verify_structures=True)

        a_lock.verify_lock(exp_q=[], exp_owner_count=0)
        a_lock.verify_lock(exp_q=[], exp_owner_count=0, verify_structures=False)
        a_lock.verify_lock(exp_q=[], exp_owner_count=0, verify_structures=True)

        a_lock.verify_lock(exp_q=[], exp_excl_wait_count=0)
        a_lock.verify_lock(exp_q=[], exp_excl_wait_count=0, verify_structures=False)
        a_lock.verify_lock(exp_q=[], exp_excl_wait_count=0, verify_structures=True)

        a_lock.verify_lock(exp_q=[], exp_owner_count=0, exp_excl_wait_count=0)
        a_lock.verify_lock(
            exp_q=[], exp_owner_count=0, exp_excl_wait_count=0, verify_structures=False
        )
        a_lock.verify_lock(
            exp_q=[], exp_owner_count=0, exp_excl_wait_count=0, verify_structures=True
        )

        a_lock.verify_lock(exp_q=[], timeout=1)
        a_lock.verify_lock(exp_q=[], timeout=1, verify_structures=False)
        a_lock.verify_lock(exp_q=[], timeout=1, verify_structures=True)

        a_lock.verify_lock(exp_q=[], exp_owner_count=0, timeout=1)
        a_lock.verify_lock(
            exp_q=[], exp_owner_count=0, timeout=1, verify_structures=False
        )
        a_lock.verify_lock(
            exp_q=[], exp_owner_count=0, timeout=1, verify_structures=True
        )

        a_lock.verify_lock(exp_q=[], exp_excl_wait_count=0, timeout=1)
        a_lock.verify_lock(
            exp_q=[], exp_excl_wait_count=0, timeout=1, verify_structures=False
        )
        a_lock.verify_lock(
            exp_q=[], exp_excl_wait_count=0, timeout=1, verify_structures=True
        )

        a_lock.verify_lock(
            exp_q=[], exp_owner_count=0, exp_excl_wait_count=0, timeout=1
        )
        a_lock.verify_lock(
            exp_q=[],
            exp_owner_count=0,
            exp_excl_wait_count=0,
            timeout=1,
            verify_structures=False,
        )
        a_lock.verify_lock(
            exp_q=[],
            exp_owner_count=0,
            exp_excl_wait_count=0,
            timeout=1,
            verify_structures=True,
        )

        for exp_owner_count in (None, 0):
            for exp_excl_wait_count in (None, 0):
                for timeout in (None, 0, 1):
                    if timeout is None:
                        for verify_structures in (None, True, False):
                            if verify_structures is None:
                                a_lock.verify_lock(
                                    exp_q=[],
                                    exp_owner_count=exp_owner_count,
                                    exp_excl_wait_count=exp_excl_wait_count,
                                )
                            else:
                                a_lock.verify_lock(
                                    exp_q=[],
                                    exp_owner_count=exp_owner_count,
                                    exp_excl_wait_count=exp_excl_wait_count,
                                    verify_structures=verify_structures,
                                )
                    else:
                        for verify_structures in (None, True, False):
                            if verify_structures is None:
                                a_lock.verify_lock(
                                    exp_q=[],
                                    exp_owner_count=exp_owner_count,
                                    exp_excl_wait_count=exp_excl_wait_count,
                                    timeout=timeout,
                                )
                            else:
                                a_lock.verify_lock(
                                    exp_q=[],
                                    exp_owner_count=exp_owner_count,
                                    exp_excl_wait_count=exp_excl_wait_count,
                                    timeout=timeout,
                                    verify_structures=verify_structures,
                                )
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_verify_lock_timeout
    ####################################################################
    def test_verify_lock_timeout(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that second obtain request fails.

        Args:
            caplog: pytest.LogCaptureFixture

        """
        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_locking.se_lock")

        a_lock = SELock()

        ml_thread = threading.current_thread()

        ml_call_seq = (
            "Request call sequence: python.py::pytest_pyfunc_call:[0-9]+ -> "
            "test_se_lock.py::TestSELockErrors.test_verify_lock_timeout:[0-9]+"
        )

        a_lock.verify_lock(exp_q=[], exp_owner_count=0, exp_excl_wait_count=0)

        # verify lock with expected q for lock not yet obtained

        ml_exp_q = [
            LockItem(
                mode=SELockObtainMode.Share,
                event_flag=True,
                thread=ml_thread,
            )
        ]

        ml_error_msg = (
            re.escape(
                f"lock_verify raising LockVerifyError. exp_q={ml_exp_q} , "
                f"lock_info.queue=[], exp_owner_count=1, "
                f"lock_info.owner_count=0, exp_excl_wait_count=0, "
                f"lock_info.excl_wait_count=0, timeout=None. "
            )
            + ml_call_seq
        )
        log_ver.add_pattern(pattern=ml_error_msg, level=logging.ERROR)

        ################################################################
        # lock empty q, no timeout
        ################################################################
        with pytest.raises(LockVerifyError, match=ml_error_msg):
            a_lock.verify_lock(
                exp_q=ml_exp_q,
                exp_owner_count=1,
                exp_excl_wait_count=0,
                verify_structures=True,
            )

        ml_error_msg = (
            re.escape(
                f"lock_verify raising LockVerifyError. exp_q={ml_exp_q} , "
                f"lock_info.queue=[], exp_owner_count=1, "
                f"lock_info.owner_count=0, exp_excl_wait_count=0, "
                f"lock_info.excl_wait_count=0, timeout=None. "
            )
            + ml_call_seq
        )
        log_ver.add_pattern(pattern=ml_error_msg, level=logging.ERROR)
        ################################################################
        # lock empty q, timeout=None
        ################################################################
        with pytest.raises(LockVerifyError, match=ml_error_msg):
            a_lock.verify_lock(
                exp_q=ml_exp_q,
                exp_owner_count=1,
                exp_excl_wait_count=0,
                verify_structures=True,
                timeout=None,
            )

        ml_error_msg = (
            re.escape(
                f"lock_verify raising LockVerifyError. exp_q={ml_exp_q} , "
                f"lock_info.queue=[], exp_owner_count=1, "
                f"lock_info.owner_count=0, exp_excl_wait_count=0, "
                f"lock_info.excl_wait_count=0, timeout=0. "
            )
            + ml_call_seq
        )
        log_ver.add_pattern(pattern=ml_error_msg, level=logging.ERROR)

        ################################################################
        # lock empty q, timeout=0
        ################################################################
        with pytest.raises(LockVerifyError, match=ml_error_msg):
            a_lock.verify_lock(
                exp_q=ml_exp_q,
                exp_owner_count=1,
                exp_excl_wait_count=0,
                verify_structures=True,
                timeout=0,
            )

        ml_error_msg = (
            re.escape(
                f"lock_verify raising LockVerifyError. exp_q={ml_exp_q} , "
                f"lock_info.queue=[], exp_owner_count=1, "
                f"lock_info.owner_count=0, exp_excl_wait_count=0, "
                f"lock_info.excl_wait_count=0, timeout=0.1. "
            )
            + ml_call_seq
        )
        log_ver.add_pattern(pattern=ml_error_msg, level=logging.ERROR)

        ################################################################
        # lock empty q, timeout=0.1
        ################################################################
        with pytest.raises(LockVerifyError, match=ml_error_msg):
            a_lock.verify_lock(
                exp_q=ml_exp_q,
                exp_owner_count=1,
                exp_excl_wait_count=0,
                verify_structures=True,
                timeout=0.1,
            )

        ml_error_msg = (
            re.escape(
                f"lock_verify raising LockVerifyError. exp_q={ml_exp_q} , "
                f"lock_info.queue=[], exp_owner_count=1, "
                f"lock_info.owner_count=0, exp_excl_wait_count=0, "
                f"lock_info.excl_wait_count=0, timeout=1. "
            )
            + ml_call_seq
        )
        log_ver.add_pattern(pattern=ml_error_msg, level=logging.ERROR)

        ################################################################
        # lock empty q, timeout=1
        ################################################################
        with pytest.raises(LockVerifyError, match=ml_error_msg):
            a_lock.verify_lock(
                exp_q=ml_exp_q,
                exp_owner_count=1,
                exp_excl_wait_count=0,
                verify_structures=True,
                timeout=1,
            )

        ml_error_msg = (
            re.escape(
                f"lock_verify raising LockVerifyError. exp_q={ml_exp_q} , "
                f"lock_info.queue=[], exp_owner_count=1, "
                f"lock_info.owner_count=0, exp_excl_wait_count=0, "
                f"lock_info.excl_wait_count=0, timeout=1.23. "
            )
            + ml_call_seq
        )
        log_ver.add_pattern(pattern=ml_error_msg, level=logging.ERROR)

        ################################################################
        # lock empty q, timeout=1.23
        ################################################################
        with pytest.raises(LockVerifyError, match=ml_error_msg):
            a_lock.verify_lock(
                exp_q=ml_exp_q,
                exp_owner_count=1,
                exp_excl_wait_count=0,
                verify_structures=True,
                timeout=1.23,
            )

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_se_lock_second_obtain
    ####################################################################
    @pytest.mark.parametrize(
        "first_request_arg",
        [
            SELock.ReqType.Exclusive,
            SELock.ReqType.ExclusiveRecursive,
            SELock.ReqType.Share,
        ],
    )
    @pytest.mark.parametrize(
        "second_request_arg",
        [
            SELock.ReqType.Exclusive,
            SELock.ReqType.ExclusiveRecursive,
            SELock.ReqType.Share,
        ],
    )
    def test_se_lock_second_obtain(
        self,
        first_request_arg: SELock.ReqType,
        second_request_arg: SELock.ReqType,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test that second obtain request fails.

        Args:
            first_request_arg: first obtain request
            second_request_arg: second obtain request
            caplog: pytest.LogCaptureFixture

        """

        ################################################################
        # mainline
        ################################################################
        if (
            second_request_arg == SELock.ReqType.ExclusiveRecursive
            and first_request_arg != SELock.ReqType.Share
        ):
            return

        log_ver = LogVer(log_name="scottbrian_locking.se_lock")

        a_lock = SELock()

        a_lock.verify_lock(exp_q=[], exp_owner_count=0, exp_excl_wait_count=0)

        ml_thread = threading.current_thread()
        ml_esc_thread_name = re.escape(ml_thread.name)

        ml_call_seq = (
            "python.py::pytest_pyfunc_call:[0-9]+ -> "
            "test_se_lock.py::TestSELockErrors.test_se_lock_second_obtain:[0-9]+"
        )

        if first_request_arg == SELock.ReqType.Exclusive:
            ml_obtain_pattern = (
                f"{first_request_arg} granted immediate exclusive "
                f"control to thread {ml_esc_thread_name}, "
                f"call sequence: {ml_call_seq}"
            )
            a_lock.obtain_excl()
            verify_mode = SELockObtainMode.Exclusive
            exp_owner_count = -1
            release_str = "exclusive"
        elif first_request_arg == SELock.ReqType.ExclusiveRecursive:
            ml_obtain_pattern = (
                f"{first_request_arg} granted "
                "immediate exclusive control with recursion depth of 1 for "
                f"thread {ml_esc_thread_name}, "
                f"call sequence: {ml_call_seq}"
            )
            a_lock.obtain_excl_recursive()
            verify_mode = SELockObtainMode.Exclusive
            exp_owner_count = -1
            release_str = "exclusive"
        else:
            ml_obtain_pattern = (
                f"{first_request_arg} granted immediate shared "
                f"control to thread {ml_esc_thread_name}, "
                f"call sequence: {ml_call_seq}"
            )
            a_lock.obtain_share()
            verify_mode = SELockObtainMode.Share
            exp_owner_count = 1
            release_str = "shared"
        log_ver.add_pattern(pattern=ml_obtain_pattern)

        a_lock.verify_lock(
            exp_q=[
                LockItem(
                    mode=verify_mode,
                    event_flag=False,
                    thread=ml_thread,
                ),
            ],
            exp_owner_count=exp_owner_count,
            exp_excl_wait_count=0,
        )

        ml_error_msg = (
            f"{second_request_arg} for thread {ml_esc_thread_name} "
            "raising SELockAlreadyOwnedError because the requestor "
            f"already owns the lock. Request call sequence: {ml_call_seq}"
        )

        log_ver.add_pattern(pattern=ml_error_msg, level=logging.ERROR)
        with pytest.raises(SELockAlreadyOwnedError, match=ml_error_msg):
            if second_request_arg == SELock.ReqType.Exclusive:
                a_lock.obtain_excl()
            elif second_request_arg == SELock.ReqType.ExclusiveRecursive:
                a_lock.obtain_excl_recursive()
            else:
                a_lock.obtain_share()

        a_lock.verify_lock(
            exp_q=[
                LockItem(
                    mode=verify_mode,
                    event_flag=False,
                    thread=ml_thread,
                ),
            ],
            exp_owner_count=exp_owner_count,
            exp_excl_wait_count=0,
        )
        ml_release_pattern = (
            f"SELock release request removed {release_str} control for thread "
            f"{ml_esc_thread_name}, "
            f"call sequence: {ml_call_seq}"
        )
        log_ver.add_pattern(pattern=ml_release_pattern)
        a_lock.release()

        a_lock.verify_lock(exp_q=[], exp_owner_count=0, exp_excl_wait_count=0)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_se_lock_multi_share
    ####################################################################
    def test_se_lock_multi_share(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test multiple share requests.

        Args:
            caplog: pytest.LogCaptureFixture

        """

        def f1(do_second_share: bool) -> None:
            """Function that obtains lock and exits still holding it.

            Args:
                do_second_share: If True, get lock again
            """
            a_lock.obtain_share()

            if do_second_share:
                f1_esc_thread_name = re.escape(f"{threading.current_thread().name}")
                f1_error_msg = (
                    f"SELock share obtain request for thread {f1_esc_thread_name} "
                    "raising SELockAlreadyOwnedError because the requestor "
                    f"already owns the lock. Request call sequence: "
                    "threading.py::Thread.run:[0-9]+ -> test_se_lock.py::f1:[0-9]+"
                )

                log_ver.add_pattern(pattern=f1_error_msg, level=logging.ERROR)
                with pytest.raises(SELockAlreadyOwnedError, match=f1_error_msg):
                    a_lock.obtain_share()

            ml_event1.set()
            ml_event2.wait()
            a_lock.release()

        ################################################################
        # mainline
        ################################################################
        a_lock = SELock()

        a_lock.logger.setLevel(logging.ERROR)
        # self.debug_logging_enabled = False

        log_ver = LogVer(log_name="scottbrian_locking.se_lock")

        a_lock.verify_lock(exp_q=[], exp_owner_count=0, exp_excl_wait_count=0)

        ml_event1 = threading.Event()
        ml_event2 = threading.Event()

        num_reqs = 100000
        join_list = []
        for idx in range(num_reqs):
            if idx == num_reqs - 1:
                second_share = True
            else:
                second_share = False
            f1_thread = threading.Thread(target=f1, args=(second_share,))
            join_list.append(f1_thread)
            f1_thread.start()
            ml_event1.wait()
            ml_event1.clear()

        assert len(a_lock.owner_wait_q) == num_reqs

        ml_event2.set()
        for item in join_list:
            item.join()

        a_lock.logger.setLevel(logging.DEBUG)
        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        # log_ver.verify_match_results(match_results)

    ####################################################################
    # test_se_lock_release_unowned_loc
    ####################################################################
    def test_se_lock_release_unowned_lock(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test release of unowned lock."""
        ################################################################
        # AttemptedReleaseOfUnownedLock
        ################################################################
        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_locking.se_lock")

        ml_error_msg = (
            "SELock release request for thread "
            f"{threading.current_thread().name} raising "
            "AttemptedReleaseOfUnownedLock because an entry on the "
            "owner-waiter queue was not found for that thread. "
            "Request call sequence: python.py::pytest_pyfunc_call:[0-9]+ "
            "-> test_se_lock.py::"
            "TestSELockErrors.test_se_lock_release_unowned_lock:[0-9]+"
        )

        log_ver.add_pattern(pattern=ml_error_msg, level=logging.ERROR)
        with pytest.raises(AttemptedReleaseOfUnownedLock, match=ml_error_msg):
            a_lock = SELock()

            a_lock.verify_lock(exp_q=[], exp_owner_count=0, exp_excl_wait_count=0)

            a_lock.release()

        a_lock.verify_lock(exp_q=[], exp_owner_count=0, exp_excl_wait_count=0)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_se_lock_release_owner_not_alive
    ####################################################################
    def test_se_lock_release_owner_not_alive(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test owner become not alive while waiting for lock."""

        ################################################################
        # SELockOwnerNotAlive
        ################################################################
        def f1() -> None:
            """Function that obtains lock and end still holding it."""
            f1_thread_name = re.escape(f"{f1_thread.name}")
            f1_pattern = (
                "SELock exclusive obtain request granted immediate exclusive "
                f"control to thread {f1_thread_name}, "
                "call sequence: threading.py::Thread.run:[0-9]+ "
                "-> test_se_lock.py::f1:[0-9]+"
            )

            log_ver.add_pattern(pattern=f1_pattern)

            a_lock.obtain_excl()

            a_lock.verify_lock(
                exp_q=[
                    LockItem(
                        mode=SELockObtainMode.Exclusive,
                        event_flag=False,
                        thread=f1_thread,
                    ),
                ],
                exp_owner_count=-1,
                exp_excl_wait_count=0,
            )

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_locking.se_lock")

        a_lock = SELock()
        a_lock.verify_lock(exp_q=[], exp_owner_count=0, exp_excl_wait_count=0)

        f1_thread = threading.Thread(target=f1)
        f1_thread.start()
        f1_thread.join()

        a_lock.verify_lock(
            exp_q=[
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f1_thread,
                ),
            ],
            exp_owner_count=-1,
            exp_excl_wait_count=0,
        )

        ml_pattern = (
            "SELock exclusive obtain request for thread "
            f"{threading.current_thread().name} waiting for SELock, timeout=None, "
            "call sequence: python.py::pytest_pyfunc_call:[0-9]+ -> "
            "test_se_lock.py::TestSELockErrors."
            "test_se_lock_release_owner_not_alive:[0-9]+"
        )

        log_ver.add_pattern(pattern=ml_pattern)

        f1_thread_str = re.escape(f"{f1_thread}")
        ml_error_msg = (
            f"SELock exclusive obtain request for thread "
            f"{threading.current_thread().name} "
            "raising SELockOwnerNotAlive while waiting for a lock because "
            f"the lock owner thread {f1_thread_str} "
            "is not alive and will thus never release the lock. "
            "Request call sequence: python.py::pytest_pyfunc_call:[0-9]+ -> "
            "test_se_lock.py::TestSELockErrors."
            "test_se_lock_release_owner_not_alive:[0-9]+"
        )

        log_ver.add_pattern(pattern=ml_error_msg, level=logging.ERROR)

        with pytest.raises(SELockOwnerNotAlive, match=ml_error_msg):
            # f1 obtained the lock and exited
            a_lock.obtain_excl()

        # the application is responsible for doing whatever recovery it
        # needs and then must release the lock
        alpha_thread = threading.current_thread()

        a_lock.verify_lock(
            exp_q=[
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f1_thread,
                ),
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=alpha_thread,
                ),
            ],
            exp_owner_count=-1,
            exp_excl_wait_count=1,
        )

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_se_lock_release_by_exclusive_waiter
    ####################################################################
    def test_se_lock_release_by_exclusive_waiter(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test release by exclusive waiter."""

        ################################################################
        # AttemptedReleaseByExclusiveWaiter
        ################################################################
        def f2() -> None:
            """Function that gets lock exclusive to cause contention."""
            # a_lock.obtain(mode=SELock._Mode.EXCL)
            f2_thread_name = re.escape(f"{f2_thread.name}")
            f2_pattern = (
                "SELock exclusive obtain request granted immediate exclusive "
                f"control to thread {f2_thread_name}, "
                "call sequence: threading.py::Thread.run:[0-9]+ "
                "-> test_se_lock.py::f2:[0-9]+"
            )

            log_ver.add_pattern(pattern=f2_pattern)

            a_lock.obtain_excl()

            a_lock.verify_lock(
                exp_q=[
                    LockItem(
                        mode=SELockObtainMode.Exclusive,
                        event_flag=False,
                        thread=f2_thread,
                    ),
                ],
                exp_owner_count=-1,
                exp_excl_wait_count=0,
            )

            a_event.set()
            a_event2.wait()

        def f3() -> None:
            """Function that tries to release lock while waiting."""
            # a_lock.obtain(mode=SELock._Mode.EXCL)
            f3_thread_name = re.escape(f"{f3_thread.name}")

            f3_call_seq = (
                "Request call sequence: threading.py::Thread.run:[0-9]+ "
                "-> test_se_lock.py::f3:[0-9]+"
            )

            f3_pattern = (
                f"SELock exclusive obtain request for thread {f3_thread_name} "
                "waiting for SELock, timeout=None, call sequence: "
                "threading.py::Thread.run:[0-9]+ -> test_se_lock.py::f3:[0-9]+"
            )
            log_ver.add_pattern(pattern=f3_pattern)

            a_lock.obtain_excl()

            f3_exp_q = [
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f2_thread,
                ),
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=True,
                    thread=f3_thread,
                ),
            ]
            a_lock.verify_lock(
                exp_q=f3_exp_q,
                exp_owner_count=-1,
                exp_excl_wait_count=1,
                verify_structures=False,
            )

            f3_error_msg = (
                re.escape(
                    "lock_verify raising LockVerifyError. owner_count_error=False, "
                    "wait_count_error=False, excl_event_flag_error=True, "
                    f"share_event_flag_error=False, exp_q={f3_exp_q}, "
                    f"lock_info.queue={f3_exp_q}, exp_owner_count=-1, "
                    "lock_info.owner_count=-1, exp_excl_wait_count=1, "
                    "lock_info.excl_wait_count=1, timeout=None, "
                    "calc_owner_count=-1, calc_excl_wait_count=1, "
                    "idx_of_first_excl_wait=1, idx_of_first_excl_event_flag=1, "
                    "idx_of_first_share_wait=-1, idx_of_first_share_event_flag=-1. "
                )
                + f3_call_seq
            )

            log_ver.add_pattern(pattern=f3_error_msg, level=logging.ERROR)
            with pytest.raises(LockVerifyError, match=f3_error_msg):
                a_lock.verify_lock(
                    exp_q=f3_exp_q,
                    exp_owner_count=-1,
                    exp_excl_wait_count=1,
                    verify_structures=True,
                )

            a_event.set()
            a_event3.wait()

            f3_error_msg = (
                f"SELock release request for thread {f3_thread_name} "
                "raising AttemptedReleaseByExclusiveWaiter because the entry found "
                "for that thread was still waiting for exclusive control of the lock. "
                "Request call sequence: threading.py::Thread.run:[0-9]+ "
                "-> test_se_lock.py::f3:[0-9]+"
            )
            log_ver.add_pattern(pattern=f3_error_msg, level=logging.ERROR)
            with pytest.raises(AttemptedReleaseByExclusiveWaiter, match=f3_error_msg):
                a_lock.release()

            a_lock.verify_lock(
                exp_q=f3_exp_q,
                exp_owner_count=-1,
                exp_excl_wait_count=1,
                verify_structures=False,
            )

            f3_error_msg = (
                re.escape(
                    "lock_verify raising LockVerifyError. owner_count_error=False, "
                    "wait_count_error=False, excl_event_flag_error=True, "
                    f"share_event_flag_error=False, exp_q=None, "
                    f"lock_info.queue={exp_q}, exp_owner_count=None, "
                    "lock_info.owner_count=-1, exp_excl_wait_count=None, "
                    "lock_info.excl_wait_count=1, timeout=None, "
                    "calc_owner_count=-1, calc_excl_wait_count=1, "
                    "idx_of_first_excl_wait=1, idx_of_first_excl_event_flag=1, "
                    "idx_of_first_share_wait=-1, idx_of_first_share_event_flag=-1. "
                )
                + f3_call_seq
            )
            log_ver.add_pattern(pattern=f3_error_msg, level=logging.ERROR)
            with pytest.raises(LockVerifyError, match=f3_error_msg):
                a_lock.verify_lock()

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_locking.se_lock")

        ml_call_seq = (
            "Request call sequence: python.py::pytest_pyfunc_call:[0-9]+ -> "
            "test_se_lock.py::TestSELockErrors."
            "test_se_lock_release_by_exclusive_waiter:[0-9]+"
        )

        a_lock = SELock()

        a_lock.verify_lock(
            exp_q=[],
            exp_owner_count=0,
            exp_excl_wait_count=0,
        )

        a_event = threading.Event()
        a_event2 = threading.Event()
        a_event3 = threading.Event()
        f2_thread = threading.Thread(target=f2)
        f3_thread = threading.Thread(target=f3)

        # start f2 to get the lock exclusive
        f2_thread.start()

        # wait for f2 to tell us it has the lock
        a_event.wait()
        a_event.clear()

        # verify lock
        a_lock.verify_lock(
            exp_q=[
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f2_thread,
                ),
            ],
            exp_owner_count=-1,
            exp_excl_wait_count=0,
        )

        # start f3 to queue up for the lock behind f2
        f3_thread.start()

        a_lock.verify_lock(
            exp_q=[
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f2_thread,
                ),
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f3_thread,
                ),
            ],
            exp_owner_count=-1,
            exp_excl_wait_count=1,
            timeout=10,
        )

        # post (prematurely) the event in the SELock for f3
        a_lock.owner_wait_q[1].event.set()

        a_event.wait()
        a_event.clear()

        exp_q = [
            LockItem(
                mode=SELockObtainMode.Exclusive,
                event_flag=False,
                thread=f2_thread,
            ),
            LockItem(
                mode=SELockObtainMode.Exclusive,
                event_flag=True,
                thread=f3_thread,
            ),
        ]

        a_lock.verify_lock(
            exp_q=exp_q,
            exp_owner_count=-1,
            exp_excl_wait_count=1,
            verify_structures=False,  # avoid error for now
        )

        mainline_error_msg = (
            re.escape(
                "lock_verify raising LockVerifyError. owner_count_error=False, "
                "wait_count_error=False, excl_event_flag_error=True, "
                f"share_event_flag_error=False, exp_q={exp_q}, "
                f"lock_info.queue={exp_q}, exp_owner_count=-1, "
                "lock_info.owner_count=-1, exp_excl_wait_count=1, "
                "lock_info.excl_wait_count=1, timeout=None, "
                "calc_owner_count=-1, calc_excl_wait_count=1, "
                "idx_of_first_excl_wait=1, idx_of_first_excl_event_flag=1, "
                "idx_of_first_share_wait=-1, idx_of_first_share_event_flag=-1. "
            )
            + ml_call_seq
        )
        log_ver.add_pattern(pattern=mainline_error_msg, level=logging.ERROR)
        with pytest.raises(LockVerifyError, match=mainline_error_msg):
            a_lock.verify_lock(
                exp_q=exp_q,
                exp_owner_count=-1,
                exp_excl_wait_count=1,
                verify_structures=True,
            )

        # tell f2 and f3 to end - we will leave the lock damaged
        a_event2.set()
        a_event3.set()

        f2_thread.join()
        f3_thread.join()

        a_lock.verify_lock(
            exp_q=exp_q,
            exp_owner_count=-1,
            exp_excl_wait_count=1,
            verify_structures=False,
        )

        mainline_error_msg = (
            re.escape(
                "lock_verify raising LockVerifyError. owner_count_error=False, "
                "wait_count_error=False, excl_event_flag_error=True, "
                f"share_event_flag_error=False, exp_q=None, "
                f"lock_info.queue={exp_q}, exp_owner_count=None, "
                "lock_info.owner_count=-1, exp_excl_wait_count=None, "
                "lock_info.excl_wait_count=1, timeout=None, "
                "calc_owner_count=-1, calc_excl_wait_count=1, "
                "idx_of_first_excl_wait=1, idx_of_first_excl_event_flag=1, "
                "idx_of_first_share_wait=-1, idx_of_first_share_event_flag=-1. "
            )
            + ml_call_seq
        )

        log_ver.add_pattern(pattern=mainline_error_msg, level=logging.ERROR)
        with pytest.raises(LockVerifyError, match=mainline_error_msg):
            a_lock.verify_lock()

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_se_lock_release_by_shared_waite
    ####################################################################
    def test_se_lock_release_by_shared_waiter(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test release by shared waiter."""

        ################################################################
        # AttemptedReleaseBySharedWaiter
        ################################################################
        def f4() -> None:
            """Function that gets lock exclusive to cause contention."""
            f4_thread_name = re.escape(f"{f4_thread.name}")
            f4_pattern = (
                "SELock exclusive obtain request granted immediate exclusive "
                f"control to thread {f4_thread_name}, "
                "call sequence: threading.py::Thread.run:[0-9]+ "
                "-> test_se_lock.py::f4:[0-9]+"
            )

            log_ver.add_pattern(pattern=f4_pattern)

            # a_lock.obtain(mode=SELock._Mode.EXCL)
            a_lock.obtain_excl()

            a_lock.verify_lock(
                exp_q=[
                    LockItem(
                        mode=SELockObtainMode.Exclusive,
                        event_flag=False,
                        thread=f4_thread,
                    ),
                ],
                exp_owner_count=-1,
                exp_excl_wait_count=0,
            )

            mainline_wait_event.set()
            f4_wait_event.wait()

        def f5() -> None:
            """Function that tries to release lock while waiting."""
            f5_thread_name = re.escape(f"{f5_thread.name}")

            f5_call_seq = (
                "Request call sequence: threading.py::Thread.run:[0-9]+ "
                "-> test_se_lock.py::f5:[0-9]+"
            )

            f5_pattern = (
                f"SELock share obtain request for thread {f5_thread_name} "
                "waiting for SELock, timeout=None, call sequence: "
                "threading.py::Thread.run:[0-9]+ -> test_se_lock.py::f5:[0-9]+"
            )
            log_ver.add_pattern(pattern=f5_pattern)

            # a_lock.obtain(mode=SELock._Mode.SHARE)
            a_lock.obtain_share()

            # we have been woken prematurely
            f5_exp_q = [
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f4_thread,
                ),
                LockItem(
                    mode=SELockObtainMode.Share,
                    event_flag=True,
                    thread=f5_thread,
                ),
            ]
            a_lock.verify_lock(
                exp_q=f5_exp_q,
                exp_owner_count=-1,
                exp_excl_wait_count=0,
                verify_structures=False,
            )

            f5_verify_error_msg = (
                re.escape(
                    "lock_verify raising LockVerifyError. owner_count_error=False, "
                    "wait_count_error=False, excl_event_flag_error=False, "
                    f"share_event_flag_error=True, exp_q={f5_exp_q}, "
                    f"lock_info.queue={f5_exp_q}, exp_owner_count=-1, "
                    "lock_info.owner_count=-1, exp_excl_wait_count=0, "
                    "lock_info.excl_wait_count=0, timeout=None, "
                    "calc_owner_count=-1, calc_excl_wait_count=0, "
                    "idx_of_first_excl_wait=-1, idx_of_first_excl_event_flag=-1, "
                    "idx_of_first_share_wait=-1, idx_of_first_share_event_flag=1. "
                )
                + f5_call_seq
            )

            log_ver.add_pattern(pattern=f5_verify_error_msg, level=logging.ERROR)
            with pytest.raises(LockVerifyError, match=f5_verify_error_msg):
                a_lock.verify_lock(
                    exp_q=f5_exp_q,
                    exp_owner_count=-1,
                    exp_excl_wait_count=0,
                    verify_structures=True,
                )

            f5_release_error_msg = (
                f"SELock release request for thread {f5_thread_name} "
                "raising AttemptedReleaseBySharedWaiter because the entry found "
                "for that thread was still waiting for shared control of the lock. "
                "Request call sequence: threading.py::Thread.run:[0-9]+ "
                "-> test_se_lock.py::f5:[0-9]+"
            )
            log_ver.add_pattern(pattern=f5_release_error_msg, level=logging.ERROR)
            with pytest.raises(
                AttemptedReleaseBySharedWaiter, match=f5_release_error_msg
            ):
                a_lock.release()

            # the lock should not have changed, and the lock_verify
            # should provide the same result as above
            log_ver.add_pattern(pattern=f5_verify_error_msg, level=logging.ERROR)
            with pytest.raises(LockVerifyError, match=f5_verify_error_msg):
                a_lock.verify_lock(
                    exp_q=f5_exp_q,
                    exp_owner_count=-1,
                    exp_excl_wait_count=0,
                    verify_structures=True,
                )

            # tell mainline we are done
            mainline_wait_event.set()
            # wait for mainline to tell us to end
            f5_wait_event.wait()

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_locking.se_lock")

        ml_call_seq = (
            "Request call sequence: python.py::pytest_pyfunc_call:[0-9]+ -> "
            "test_se_lock.py::TestSELockErrors."
            "test_se_lock_release_by_shared_waiter:[0-9]+"
        )

        a_lock = SELock()

        a_lock.verify_lock(
            exp_q=[],
            exp_owner_count=0,
            exp_excl_wait_count=0,
        )

        mainline_wait_event = threading.Event()
        f4_wait_event = threading.Event()
        f5_wait_event = threading.Event()
        f4_thread = threading.Thread(target=f4)
        f5_thread = threading.Thread(target=f5)

        # start f4 to get the lock exclusive
        f4_thread.start()

        # wait for f4 to tell us it has the lock
        mainline_wait_event.wait()
        mainline_wait_event.clear()

        # verify lock
        a_lock.verify_lock(
            exp_q=[
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f4_thread,
                ),
            ],
            exp_owner_count=-1,
            exp_excl_wait_count=0,
        )

        # start f5 to queue up for the lock behind f4
        f5_thread.start()

        # loop 10 secs until verify_lock sees both locks in the queue
        a_lock.verify_lock(
            exp_q=[
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f4_thread,
                ),
                LockItem(
                    mode=SELockObtainMode.Share,
                    event_flag=False,
                    thread=f5_thread,
                ),
            ],
            exp_owner_count=-1,
            exp_excl_wait_count=0,
            timeout=10,
        )

        # post (prematurely) the event in the SELock for f5
        a_lock.owner_wait_q[1].event.set()

        # wait for f5 to tell us it did the release
        mainline_wait_event.wait()
        mainline_wait_event.clear()

        exp_q = [
            LockItem(
                mode=SELockObtainMode.Exclusive,
                event_flag=False,
                thread=f4_thread,
            ),
            LockItem(
                mode=SELockObtainMode.Share,
                event_flag=True,
                thread=f5_thread,
            ),
        ]
        a_lock.verify_lock(
            exp_q=exp_q,
            exp_owner_count=-1,
            exp_excl_wait_count=0,
            verify_structures=False,
        )

        mainline_error_msg = (
            re.escape(
                "lock_verify raising LockVerifyError. owner_count_error=False, "
                "wait_count_error=False, excl_event_flag_error=False, "
                f"share_event_flag_error=True, exp_q={exp_q}, "
                f"lock_info.queue={exp_q}, exp_owner_count=-1, "
                "lock_info.owner_count=-1, exp_excl_wait_count=0, "
                "lock_info.excl_wait_count=0, timeout=None, "
                "calc_owner_count=-1, calc_excl_wait_count=0, "
                "idx_of_first_excl_wait=-1, idx_of_first_excl_event_flag=-1, "
                "idx_of_first_share_wait=-1, idx_of_first_share_event_flag=1. "
            )
            + ml_call_seq
        )

        log_ver.add_pattern(pattern=mainline_error_msg, level=logging.ERROR)
        with pytest.raises(LockVerifyError, match=mainline_error_msg):
            a_lock.verify_lock(
                exp_q=exp_q,
                exp_owner_count=-1,
                exp_excl_wait_count=0,
                verify_structures=True,
            )

        # tell f4 and f5 to end - we will leave the lock damaged
        f4_wait_event.set()
        f5_wait_event.set()

        f4_thread.join()
        f5_thread.join()

        # the lock should not have changed, and the lock_verify
        # should provide the same result as above, except that we need
        # to set the exp_q here to get the current status of the threads
        # which are now in a stopped state

        exp_q = [
            LockItem(
                mode=SELockObtainMode.Exclusive,
                event_flag=False,
                thread=f4_thread,
            ),
            LockItem(
                mode=SELockObtainMode.Share,
                event_flag=True,
                thread=f5_thread,
            ),
        ]
        mainline_error_msg = (
            re.escape(
                "lock_verify raising LockVerifyError. owner_count_error=False, "
                "wait_count_error=False, excl_event_flag_error=False, "
                f"share_event_flag_error=True, exp_q={exp_q}, "
                f"lock_info.queue={exp_q}, exp_owner_count=-1, "
                "lock_info.owner_count=-1, exp_excl_wait_count=0, "
                "lock_info.excl_wait_count=0, timeout=None, "
                "calc_owner_count=-1, calc_excl_wait_count=0, "
                "idx_of_first_excl_wait=-1, idx_of_first_excl_event_flag=-1, "
                "idx_of_first_share_wait=-1, idx_of_first_share_event_flag=1. "
            )
            + ml_call_seq
        )
        log_ver.add_pattern(pattern=mainline_error_msg, level=logging.ERROR)
        with pytest.raises(LockVerifyError, match=mainline_error_msg):
            a_lock.verify_lock(
                exp_q=exp_q,
                exp_owner_count=-1,
                exp_excl_wait_count=0,
                verify_structures=True,
            )

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)


########################################################################
# TestSELockBasic class to test SELock methods
########################################################################
class TestSELockBasic:
    """Class TestSELockBasic."""

    ####################################################################
    # test_se_wait_time_race
    ####################################################################
    @pytest.mark.parametrize("timeout_arg", (0, 0.5, 1))
    def test_se_wait_time_race(self, timeout_arg: float) -> None:
        """Force timeout path in wait_for_lock.

        We want to timeout in SELock._wait_for_timeout and then, after
        getting the se_lock_lock, we discover that the event is now
        posted and return to grant the lock. We will do this by getting
        to se_lock_lock here to force the path.

        Args:
            timeout_arg: 0 = no timeout, else num seconds to timeout

        """

        def f1() -> None:
            a_lock.obtain_excl()
            ml_event1.set()
            ml_event2.wait()
            a_lock.release()

        def f2() -> None:
            if timeout_arg == 0:
                a_lock.obtain_excl()
            else:
                a_lock.obtain_excl(timeout=timeout_arg)
            a_lock.release()

        ################################################################
        # mainline
        ################################################################
        a_lock = SELock()

        ml_event1 = threading.Event()
        ml_event2 = threading.Event()

        f1_thread = threading.Thread(target=f1)
        f2_thread = threading.Thread(target=f2)

        f1_thread.start()

        ml_event1.wait()

        f2_thread.start()

        with a_lock.se_lock_lock:
            ml_event2.set()
            if timeout_arg == 0:
                time.sleep(4)
            else:
                time.sleep(timeout_arg + 1)

        f1_thread.join()
        f2_thread.join()

    ####################################################################
    # test_se_lock_repr
    ####################################################################
    def test_se_lock_repr(self) -> None:
        """Test the repr of SELock."""
        a_se_lock = SELock()

        expected_repr_str = "SELock()"

        assert repr(a_se_lock) == expected_repr_str

    ####################################################################
    # test_se_lock_obtain_excl
    ####################################################################
    @pytest.mark.parametrize(
        "ml_context_arg",
        [
            ContextArg.NoContext,
            ContextArg.ContextExclShare,
            ContextArg.ContextObtain,
        ],
    )
    def test_se_lock_obtain_excl(
        self,
        ml_context_arg: ContextArg,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test exclusive lock obtain.

        Args:
            ml_context_arg: specifies the type of obtain to do

        """

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_locking.se_lock")

        log_ver.test_msg("mainline entry")

        if ml_context_arg == ContextArg.NoContext:
            ml_excl_call_seq = (
                "python.py::pytest_pyfunc_call:[0-9]+ "
                "-> test_se_lock.py::TestSELockBasic.test_se_lock_obtain_excl:[0-9]+"
            )
            ml_release_call_seq = ml_excl_call_seq

        elif ml_context_arg == ContextArg.ContextExclShare:
            ml_excl_call_seq = (
                "test_se_lock.py::TestSELockBasic.test_se_lock_obtain_excl:[0-9]+ "
                "-> se_lock.py::SELockExcl.__enter__:[0-9]+"
            )
            ml_release_call_seq = (
                "test_se_lock.py::TestSELockBasic.test_se_lock_obtain_excl:[0-9]+ "
                "-> se_lock.py::SELockExcl.__exit__:[0-9]+"
            )

        else:
            ml_excl_call_seq = (
                "test_se_lock.py::TestSELockBasic.test_se_lock_obtain_excl:[0-9]+ "
                "-> se_lock.py::SELockObtain.__enter__:[0-9]+"
            )
            ml_release_call_seq = (
                "test_se_lock.py::TestSELockBasic.test_se_lock_obtain_excl:[0-9]+ "
                "-> se_lock.py::SELockObtain.__exit__:[0-9]+"
            )

        ml_thread = threading.current_thread()
        ml_thread_name = ml_thread.name

        a_se_lock = SELock()

        ################################################################
        # steps 1-2
        # 1: obtain
        # 2: release
        ################################################################
        log_ver.test_msg("about to do step 1")

        ml_esc_thread_name = re.escape(f"{ml_thread.name}")
        ml_excl_obtain_pattern = (
            "SELock exclusive obtain request granted immediate exclusive "
            f"control to thread {ml_esc_thread_name}, "
            f"call sequence: {ml_excl_call_seq}"
        )

        log_ver.add_pattern(pattern=ml_excl_obtain_pattern)

        log_ver.test_msg("about to do step 2")

        ml_excl_release_pattern = (
            f"SELock release request removed exclusive control for thread "
            f"{ml_esc_thread_name}, "
            f"call sequence: {ml_release_call_seq}"
        )
        log_ver.add_pattern(pattern=ml_excl_release_pattern)

        if ml_context_arg == ContextArg.NoContext:
            a_se_lock.obtain_excl()
            obt_lock_info = a_se_lock.get_info()
            a_se_lock.release()

        elif ml_context_arg == ContextArg.ContextExclShare:
            with SELockExcl(a_se_lock):
                obt_lock_info = a_se_lock.get_info()

        else:
            with SELockObtain(a_se_lock, obtain_mode=SELockObtainMode.Exclusive):
                obt_lock_info = a_se_lock.get_info()

        assert len(obt_lock_info.queue) == 1
        assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
        assert obt_lock_info.queue[0].thread.name == ml_thread_name
        assert not obt_lock_info.queue[0].event_flag
        assert obt_lock_info.owner_count == -1
        assert obt_lock_info.excl_wait_count == 0

        rel_lock_info = a_se_lock.get_info()
        assert len(rel_lock_info.queue) == 0
        assert rel_lock_info.owner_count == 0
        assert rel_lock_info.excl_wait_count == 0

        ################################################################
        # steps 3-4
        # 3: recursive obtain
        # 4: release
        ################################################################
        log_ver.test_msg("about to do step 3")

        ml_recursive_obtain_pattern = (
            "SELock exclusive recursive obtain request granted "
            "immediate exclusive control with recursion depth of 1 for "
            f"thread {ml_esc_thread_name}, "
            f"call sequence: {ml_excl_call_seq}"
        )
        log_ver.add_pattern(pattern=ml_recursive_obtain_pattern)

        log_ver.test_msg("about to do step 4")

        log_ver.add_pattern(pattern=ml_excl_release_pattern)

        if ml_context_arg == ContextArg.NoContext:
            a_se_lock.obtain_excl_recursive()
            obt_lock_info = a_se_lock.get_info()
            a_se_lock.release()

        elif ml_context_arg == ContextArg.ContextExclShare:
            with SELockExcl(a_se_lock, allow_recursive_obtain=True):
                obt_lock_info = a_se_lock.get_info()

        else:
            with SELockObtain(
                a_se_lock,
                obtain_mode=SELockObtainMode.Exclusive,
                allow_recursive_obtain=True,
            ):
                obt_lock_info = a_se_lock.get_info()

        assert len(obt_lock_info.queue) == 1
        assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
        assert obt_lock_info.queue[0].thread.name == ml_thread_name
        assert not obt_lock_info.queue[0].event_flag
        assert obt_lock_info.owner_count == -1
        assert obt_lock_info.excl_wait_count == 0

        rel_lock_info = a_se_lock.get_info()
        assert len(rel_lock_info.queue) == 0
        assert rel_lock_info.owner_count == 0
        assert rel_lock_info.excl_wait_count == 0

        ################################################################
        # steps 5-8
        # 5: obtain
        # 6: recursive obtain
        # 7: release
        # 8: release
        ################################################################
        log_ver.test_msg("about to do step 5")

        log_ver.add_pattern(pattern=ml_excl_obtain_pattern)

        log_ver.test_msg("about to do step 6")

        ml_recursive_excl_continue_pattern_to_2 = (
            "SELock exclusive recursive obtain request continues "
            "exclusive control with recursion depth increased to 2 "
            f"for thread {ml_esc_thread_name}, "
            f"call sequence: {ml_excl_call_seq}"
        )
        log_ver.add_pattern(pattern=ml_recursive_excl_continue_pattern_to_2)

        log_ver.test_msg("about to do step 7")

        ml_recursive_release_pattern_to_1 = (
            "SELock release request continues "
            "exclusive control with recursion depth reduced to 1 "
            f"for thread {ml_esc_thread_name}, "
            f"call sequence: {ml_release_call_seq}"
        )
        log_ver.add_pattern(pattern=ml_recursive_release_pattern_to_1)

        log_ver.test_msg("about to do step 8")

        log_ver.add_pattern(pattern=ml_excl_release_pattern)

        if ml_context_arg == ContextArg.NoContext:
            a_se_lock.obtain_excl()
            obt_lock_info = a_se_lock.get_info()

            assert len(obt_lock_info.queue) == 1
            assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
            assert obt_lock_info.queue[0].thread.name == ml_thread_name
            assert not obt_lock_info.queue[0].event_flag
            assert obt_lock_info.owner_count == -1
            assert obt_lock_info.excl_wait_count == 0

            a_se_lock.obtain_excl_recursive()

            obt_lock_info = a_se_lock.get_info()
            assert len(obt_lock_info.queue) == 1
            assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
            assert obt_lock_info.queue[0].thread.name == ml_thread_name
            assert not obt_lock_info.queue[0].event_flag
            assert obt_lock_info.owner_count == -2
            assert obt_lock_info.excl_wait_count == 0

            a_se_lock.release()

            rel_lock_info = a_se_lock.get_info()

            assert len(rel_lock_info.queue) == 1
            assert rel_lock_info.queue[0].mode == SELockObtainMode.Exclusive
            assert rel_lock_info.queue[0].thread.name == ml_thread_name
            assert not rel_lock_info.queue[0].event_flag
            assert rel_lock_info.owner_count == -1
            assert rel_lock_info.excl_wait_count == 0

            a_se_lock.release()

        elif ml_context_arg == ContextArg.ContextExclShare:
            with SELockExcl(a_se_lock, allow_recursive_obtain=False):
                obt_lock_info = a_se_lock.get_info()

                assert len(obt_lock_info.queue) == 1
                assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
                assert obt_lock_info.queue[0].thread.name == ml_thread_name
                assert not obt_lock_info.queue[0].event_flag
                assert obt_lock_info.owner_count == -1
                assert obt_lock_info.excl_wait_count == 0

                with SELockExcl(a_se_lock, allow_recursive_obtain=True):
                    obt_lock_info = a_se_lock.get_info()

                    assert len(obt_lock_info.queue) == 1
                    assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
                    assert obt_lock_info.queue[0].thread.name == ml_thread_name
                    assert not obt_lock_info.queue[0].event_flag
                    assert obt_lock_info.owner_count == -2
                    assert obt_lock_info.excl_wait_count == 0

                rel_lock_info = a_se_lock.get_info()

                assert len(rel_lock_info.queue) == 1
                assert rel_lock_info.queue[0].mode == SELockObtainMode.Exclusive
                assert rel_lock_info.queue[0].thread.name == ml_thread_name
                assert not rel_lock_info.queue[0].event_flag
                assert rel_lock_info.owner_count == -1
                assert rel_lock_info.excl_wait_count == 0

        else:
            with SELockObtain(
                a_se_lock,
                obtain_mode=SELockObtainMode.Exclusive,
                allow_recursive_obtain=False,
            ):
                obt_lock_info = a_se_lock.get_info()

                assert len(obt_lock_info.queue) == 1
                assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
                assert obt_lock_info.queue[0].thread.name == ml_thread_name
                assert not obt_lock_info.queue[0].event_flag
                assert obt_lock_info.owner_count == -1
                assert obt_lock_info.excl_wait_count == 0

                with SELockObtain(
                    a_se_lock,
                    obtain_mode=SELockObtainMode.Exclusive,
                    allow_recursive_obtain=True,
                ):
                    obt_lock_info = a_se_lock.get_info()

                    assert len(obt_lock_info.queue) == 1
                    assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
                    assert obt_lock_info.queue[0].thread.name == ml_thread_name
                    assert not obt_lock_info.queue[0].event_flag
                    assert obt_lock_info.owner_count == -2
                    assert obt_lock_info.excl_wait_count == 0

                rel_lock_info = a_se_lock.get_info()

                assert len(rel_lock_info.queue) == 1
                assert rel_lock_info.queue[0].mode == SELockObtainMode.Exclusive
                assert rel_lock_info.queue[0].thread.name == ml_thread_name
                assert not rel_lock_info.queue[0].event_flag
                assert rel_lock_info.owner_count == -1
                assert rel_lock_info.excl_wait_count == 0

        rel_lock_info = a_se_lock.get_info()
        assert len(rel_lock_info.queue) == 0
        assert rel_lock_info.owner_count == 0
        assert rel_lock_info.excl_wait_count == 0

        ################################################################
        # steps 9-12
        # 09: recursive obtain
        # 10: recursive obtain
        # 11: release
        # 12: release
        ################################################################

        log_ver.test_msg("about to do step 9")

        log_ver.add_pattern(pattern=ml_recursive_obtain_pattern)

        log_ver.test_msg("about to do step 10")

        log_ver.add_pattern(pattern=ml_recursive_excl_continue_pattern_to_2)

        log_ver.test_msg("about to do step 11")

        log_ver.add_pattern(pattern=ml_recursive_release_pattern_to_1)

        log_ver.test_msg("about to do step 12")

        log_ver.add_pattern(pattern=ml_excl_release_pattern)

        if ml_context_arg == ContextArg.NoContext:
            a_se_lock.obtain_excl_recursive()

            obt_lock_info = a_se_lock.get_info()
            assert len(obt_lock_info.queue) == 1
            assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
            assert obt_lock_info.queue[0].thread.name == ml_thread_name
            assert not obt_lock_info.queue[0].event_flag
            assert obt_lock_info.owner_count == -1
            assert obt_lock_info.excl_wait_count == 0

            a_se_lock.obtain_excl_recursive()

            obt_lock_info = a_se_lock.get_info()
            assert len(obt_lock_info.queue) == 1
            assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
            assert obt_lock_info.queue[0].thread.name == ml_thread_name
            assert not obt_lock_info.queue[0].event_flag
            assert obt_lock_info.owner_count == -2
            assert obt_lock_info.excl_wait_count == 0

            a_se_lock.release()

            rel_lock_info = a_se_lock.get_info()

            assert len(rel_lock_info.queue) == 1
            assert rel_lock_info.queue[0].mode == SELockObtainMode.Exclusive
            assert rel_lock_info.queue[0].thread.name == ml_thread_name
            assert not rel_lock_info.queue[0].event_flag
            assert rel_lock_info.owner_count == -1
            assert rel_lock_info.excl_wait_count == 0

            a_se_lock.release()

        elif ml_context_arg == ContextArg.ContextExclShare:
            with SELockExcl(a_se_lock, allow_recursive_obtain=True):
                obt_lock_info = a_se_lock.get_info()

                assert len(obt_lock_info.queue) == 1
                assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
                assert obt_lock_info.queue[0].thread.name == ml_thread_name
                assert not obt_lock_info.queue[0].event_flag
                assert obt_lock_info.owner_count == -1
                assert obt_lock_info.excl_wait_count == 0

                with SELockExcl(a_se_lock, allow_recursive_obtain=True):
                    obt_lock_info = a_se_lock.get_info()

                    assert len(obt_lock_info.queue) == 1
                    assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
                    assert obt_lock_info.queue[0].thread.name == ml_thread_name
                    assert not obt_lock_info.queue[0].event_flag
                    assert obt_lock_info.owner_count == -2
                    assert obt_lock_info.excl_wait_count == 0

                rel_lock_info = a_se_lock.get_info()

                assert len(rel_lock_info.queue) == 1
                assert rel_lock_info.queue[0].mode == SELockObtainMode.Exclusive
                assert rel_lock_info.queue[0].thread.name == ml_thread_name
                assert not rel_lock_info.queue[0].event_flag
                assert rel_lock_info.owner_count == -1
                assert rel_lock_info.excl_wait_count == 0

        else:
            with SELockObtain(
                a_se_lock,
                obtain_mode=SELockObtainMode.Exclusive,
                allow_recursive_obtain=True,
            ):
                obt_lock_info = a_se_lock.get_info()

                assert len(obt_lock_info.queue) == 1
                assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
                assert obt_lock_info.queue[0].thread.name == ml_thread_name
                assert not obt_lock_info.queue[0].event_flag
                assert obt_lock_info.owner_count == -1
                assert obt_lock_info.excl_wait_count == 0

                with SELockObtain(
                    a_se_lock,
                    obtain_mode=SELockObtainMode.Exclusive,
                    allow_recursive_obtain=True,
                ):
                    obt_lock_info = a_se_lock.get_info()

                    assert len(obt_lock_info.queue) == 1
                    assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
                    assert obt_lock_info.queue[0].thread.name == ml_thread_name
                    assert not obt_lock_info.queue[0].event_flag
                    assert obt_lock_info.owner_count == -2
                    assert obt_lock_info.excl_wait_count == 0

                rel_lock_info = a_se_lock.get_info()

                assert len(rel_lock_info.queue) == 1
                assert rel_lock_info.queue[0].mode == SELockObtainMode.Exclusive
                assert rel_lock_info.queue[0].thread.name == ml_thread_name
                assert not rel_lock_info.queue[0].event_flag
                assert rel_lock_info.owner_count == -1
                assert rel_lock_info.excl_wait_count == 0

        lock_info = a_se_lock.get_info()
        assert len(lock_info.queue) == 0
        assert lock_info.owner_count == 0

        ################################################################
        # steps 13-12
        # 13: obtain
        # 14: recursive obtain
        # 15: recursive obtain
        # 16: release
        # 17: release
        # 18: release
        ################################################################
        log_ver.test_msg("about to do step 13")

        log_ver.add_pattern(pattern=ml_excl_obtain_pattern)

        log_ver.test_msg("about to do step 14")

        log_ver.add_pattern(pattern=ml_recursive_excl_continue_pattern_to_2)

        log_ver.test_msg("about to do step 15")

        ml_recursive_excl_continue_pattern_to_3 = (
            "SELock exclusive recursive obtain request continues "
            "exclusive control with recursion depth increased to 3 "
            f"for thread {ml_esc_thread_name}, "
            f"call sequence: {ml_excl_call_seq}"
        )
        log_ver.add_pattern(pattern=ml_recursive_excl_continue_pattern_to_3)

        log_ver.test_msg("about to do step 16")

        ml_recursive_release_pattern_to_2 = (
            "SELock release request continues "
            "exclusive control with recursion depth reduced to 2 "
            f"for thread {ml_esc_thread_name}, "
            f"call sequence: {ml_release_call_seq}"
        )
        log_ver.add_pattern(pattern=ml_recursive_release_pattern_to_2)

        log_ver.test_msg("about to do step 17")

        log_ver.add_pattern(pattern=ml_recursive_release_pattern_to_1)

        log_ver.test_msg("about to do step 18")

        log_ver.add_pattern(pattern=ml_excl_release_pattern)

        if ml_context_arg == ContextArg.NoContext:
            a_se_lock.obtain_excl()

            obt_lock_info = a_se_lock.get_info()
            assert len(obt_lock_info.queue) == 1
            assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
            assert obt_lock_info.queue[0].thread.name == ml_thread_name
            assert not obt_lock_info.queue[0].event_flag
            assert obt_lock_info.owner_count == -1
            assert obt_lock_info.excl_wait_count == 0

            a_se_lock.obtain_excl_recursive()

            obt_lock_info = a_se_lock.get_info()
            assert len(obt_lock_info.queue) == 1
            assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
            assert obt_lock_info.queue[0].thread.name == ml_thread_name
            assert not obt_lock_info.queue[0].event_flag
            assert obt_lock_info.owner_count == -2
            assert obt_lock_info.excl_wait_count == 0

            a_se_lock.obtain_excl_recursive()

            obt_lock_info = a_se_lock.get_info()
            assert len(obt_lock_info.queue) == 1
            assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
            assert obt_lock_info.queue[0].thread.name == ml_thread_name
            assert not obt_lock_info.queue[0].event_flag
            assert obt_lock_info.owner_count == -3
            assert obt_lock_info.excl_wait_count == 0

            a_se_lock.release()

            rel_lock_info = a_se_lock.get_info()

            assert len(rel_lock_info.queue) == 1
            assert rel_lock_info.queue[0].mode == SELockObtainMode.Exclusive
            assert rel_lock_info.queue[0].thread.name == ml_thread_name
            assert not rel_lock_info.queue[0].event_flag
            assert rel_lock_info.owner_count == -2
            assert rel_lock_info.excl_wait_count == 0

            a_se_lock.release()

            rel_lock_info = a_se_lock.get_info()

            assert len(rel_lock_info.queue) == 1
            assert rel_lock_info.queue[0].mode == SELockObtainMode.Exclusive
            assert rel_lock_info.queue[0].thread.name == ml_thread_name
            assert not rel_lock_info.queue[0].event_flag
            assert rel_lock_info.owner_count == -1
            assert rel_lock_info.excl_wait_count == 0

            a_se_lock.release()

        elif ml_context_arg == ContextArg.ContextExclShare:
            with SELockExcl(a_se_lock, allow_recursive_obtain=False):
                obt_lock_info = a_se_lock.get_info()

                assert len(obt_lock_info.queue) == 1
                assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
                assert obt_lock_info.queue[0].thread.name == ml_thread_name
                assert not obt_lock_info.queue[0].event_flag
                assert obt_lock_info.owner_count == -1
                assert obt_lock_info.excl_wait_count == 0

                with SELockExcl(a_se_lock, allow_recursive_obtain=True):
                    obt_lock_info = a_se_lock.get_info()

                    assert len(obt_lock_info.queue) == 1
                    assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
                    assert obt_lock_info.queue[0].thread.name == ml_thread_name
                    assert not obt_lock_info.queue[0].event_flag
                    assert obt_lock_info.owner_count == -2
                    assert obt_lock_info.excl_wait_count == 0

                    with SELockExcl(a_se_lock, allow_recursive_obtain=True):
                        obt_lock_info = a_se_lock.get_info()

                        assert len(obt_lock_info.queue) == 1
                        assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
                        assert obt_lock_info.queue[0].thread.name == ml_thread_name
                        assert not obt_lock_info.queue[0].event_flag
                        assert obt_lock_info.owner_count == -3
                        assert obt_lock_info.excl_wait_count == 0

                    rel_lock_info = a_se_lock.get_info()

                    assert len(rel_lock_info.queue) == 1
                    assert rel_lock_info.queue[0].mode == SELockObtainMode.Exclusive
                    assert rel_lock_info.queue[0].thread.name == ml_thread_name
                    assert not rel_lock_info.queue[0].event_flag
                    assert rel_lock_info.owner_count == -2
                    assert rel_lock_info.excl_wait_count == 0

                rel_lock_info = a_se_lock.get_info()

                assert len(rel_lock_info.queue) == 1
                assert rel_lock_info.queue[0].mode == SELockObtainMode.Exclusive
                assert rel_lock_info.queue[0].thread.name == ml_thread_name
                assert not rel_lock_info.queue[0].event_flag
                assert rel_lock_info.owner_count == -1
                assert rel_lock_info.excl_wait_count == 0

        else:
            with SELockObtain(
                a_se_lock,
                obtain_mode=SELockObtainMode.Exclusive,
                allow_recursive_obtain=False,
            ):
                obt_lock_info = a_se_lock.get_info()

                assert len(obt_lock_info.queue) == 1
                assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
                assert obt_lock_info.queue[0].thread.name == ml_thread_name
                assert not obt_lock_info.queue[0].event_flag
                assert obt_lock_info.owner_count == -1
                assert obt_lock_info.excl_wait_count == 0

                with SELockObtain(
                    a_se_lock,
                    obtain_mode=SELockObtainMode.Exclusive,
                    allow_recursive_obtain=True,
                ):
                    obt_lock_info = a_se_lock.get_info()

                    assert len(obt_lock_info.queue) == 1
                    assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
                    assert obt_lock_info.queue[0].thread.name == ml_thread_name
                    assert not obt_lock_info.queue[0].event_flag
                    assert obt_lock_info.owner_count == -2
                    assert obt_lock_info.excl_wait_count == 0

                    with SELockObtain(
                        a_se_lock,
                        obtain_mode=SELockObtainMode.Exclusive,
                        allow_recursive_obtain=True,
                    ):
                        obt_lock_info = a_se_lock.get_info()

                        assert len(obt_lock_info.queue) == 1
                        assert obt_lock_info.queue[0].mode == SELockObtainMode.Exclusive
                        assert obt_lock_info.queue[0].thread.name == ml_thread_name
                        assert not obt_lock_info.queue[0].event_flag
                        assert obt_lock_info.owner_count == -3
                        assert obt_lock_info.excl_wait_count == 0

                    rel_lock_info = a_se_lock.get_info()

                    assert len(rel_lock_info.queue) == 1
                    assert rel_lock_info.queue[0].mode == SELockObtainMode.Exclusive
                    assert rel_lock_info.queue[0].thread.name == ml_thread_name
                    assert not rel_lock_info.queue[0].event_flag
                    assert rel_lock_info.owner_count == -2
                    assert rel_lock_info.excl_wait_count == 0

                rel_lock_info = a_se_lock.get_info()

                assert len(rel_lock_info.queue) == 1
                assert rel_lock_info.queue[0].mode == SELockObtainMode.Exclusive
                assert rel_lock_info.queue[0].thread.name == ml_thread_name
                assert not rel_lock_info.queue[0].event_flag
                assert rel_lock_info.owner_count == -1
                assert rel_lock_info.excl_wait_count == 0

        lock_info = a_se_lock.get_info()
        assert len(lock_info.queue) == 0
        assert lock_info.owner_count == 0

        log_ver.test_msg("mainline exit")

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_se_lock_release_by_excl_owner
    ####################################################################
    def test_se_lock_release_by_excl_owner(
        self,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Test release by shared waiter."""

        ################################################################
        # AttemptedReleaseBySharedWaiter
        ################################################################
        def f4() -> None:
            """Function that gets lock exclusive to cause contention."""

            f4_esc_thread_name = re.escape(f"{f4_thread.name}")
            f4_excl_obtain_pattern = (
                "SELock exclusive obtain request granted immediate exclusive "
                f"control to thread {f4_esc_thread_name}, "
                "call sequence: threading.py::Thread.run:[0-9]+ "
                "-> test_se_lock.py::f4:[0-9]+"
            )

            log_ver.add_pattern(pattern=f4_excl_obtain_pattern)

            # a_lock.obtain(mode=SELock._Mode.EXCL)
            a_lock.obtain_excl()

            a_lock.verify_lock(
                exp_q=[
                    LockItem(
                        mode=SELockObtainMode.Exclusive,
                        event_flag=False,
                        thread=f4_thread,
                    ),
                ],
                exp_owner_count=-1,
                exp_excl_wait_count=0,
            )

            mainline_wait_event.set()
            f4_wait_event.wait()

            f4_exp_q = [
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f4_thread,
                ),
                LockItem(
                    mode=SELockObtainMode.Share,
                    event_flag=False,
                    thread=f5_thread,
                ),
            ]

            a_lock.verify_lock(
                exp_q=f4_exp_q,
                exp_owner_count=-1,
                exp_excl_wait_count=0,
                verify_structures=True,
            )

            f4_excl_release_pattern = (
                f"SELock release request removed exclusive control for thread "
                f"{f4_esc_thread_name}, "
                "call sequence: threading.py::Thread.run:[0-9]+ "
                "-> test_se_lock.py::f4:[0-9]+"
            )
            log_ver.add_pattern(pattern=f4_excl_release_pattern)

            f5_esc_thread = re.escape(f"{f5_thread}")
            f5_release_grant_pattern = (
                "SELock release request for thread "
                f"{f4_esc_thread_name} "
                f"granted shared control to waiting "
                f"thread {f5_esc_thread}, "
                "call sequence: threading.py::Thread.run:[0-9]+ "
                "-> test_se_lock.py::f4:[0-9]+"
            )
            log_ver.add_pattern(pattern=f5_release_grant_pattern)

            a_lock.release()

            a_lock.verify_lock(
                exp_q=[
                    LockItem(
                        mode=SELockObtainMode.Share,
                        event_flag=True,
                        thread=f5_thread,
                    )
                ],
                exp_owner_count=1,
                exp_excl_wait_count=0,
                verify_structures=True,
            )

            # tell mainline we are done
            mainline_wait_event.set()

        def f5() -> None:
            """Function that tries to release lock while waiting."""

            f5_esc_thread_name = re.escape(f"{f5_thread.name}")
            f5_excl_wait_pattern = (
                f"SELock share obtain request for thread {f5_esc_thread_name} "
                "waiting for SELock, timeout=None, call sequence: "
                "threading.py::Thread.run:[0-9]+ -> test_se_lock.py::f5:[0-9]+"
            )
            log_ver.add_pattern(pattern=f5_excl_wait_pattern)

            # a_lock.obtain(mode=SELock._Mode.SHARE)
            a_lock.obtain_share()

            # we have been woken normally
            a_lock.verify_lock(
                exp_q=[
                    LockItem(
                        mode=SELockObtainMode.Share,
                        event_flag=True,
                        thread=f5_thread,
                    )
                ],
                exp_owner_count=1,
                exp_excl_wait_count=0,
                verify_structures=True,
            )

            f5_wait_event.wait()

            f5_excl_release_pattern = (
                f"SELock release request removed shared control for thread "
                f"{f5_esc_thread_name}, "
                "call sequence: threading.py::Thread.run:[0-9]+ "
                "-> test_se_lock.py::f5:[0-9]+"
            )
            log_ver.add_pattern(pattern=f5_excl_release_pattern)

            a_lock.release()

            a_lock.verify_lock(
                exp_q=[],
                exp_owner_count=0,
                exp_excl_wait_count=0,
                verify_structures=True,
            )

            # tell mainline we are done
            mainline_wait_event.set()

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_locking.se_lock")

        a_lock = SELock()

        a_lock.verify_lock(
            exp_q=[],
            exp_owner_count=0,
            exp_excl_wait_count=0,
        )

        mainline_wait_event = threading.Event()
        f4_wait_event = threading.Event()
        f5_wait_event = threading.Event()
        f4_thread = threading.Thread(target=f4)
        f5_thread = threading.Thread(target=f5)

        # start f4 to get the lock exclusive
        f4_thread.start()

        # wait for f4 to tell us it has the lock
        mainline_wait_event.wait()
        mainline_wait_event.clear()

        # verify lock
        a_lock.verify_lock(
            exp_q=[
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f4_thread,
                ),
            ],
            exp_owner_count=-1,
            exp_excl_wait_count=0,
        )

        # start f5 to queue up for the lock behind f4
        f5_thread.start()

        # loop 10 secs until verify_lock sees both locks in the queue
        a_lock.verify_lock(
            exp_q=[
                LockItem(
                    mode=SELockObtainMode.Exclusive,
                    event_flag=False,
                    thread=f4_thread,
                ),
                LockItem(
                    mode=SELockObtainMode.Share,
                    event_flag=False,
                    thread=f5_thread,
                ),
            ],
            exp_owner_count=-1,
            exp_excl_wait_count=0,
            timeout=10,
        )

        # post f4 to release the excl lock
        f4_wait_event.set()

        # wait for f4 to tell us it did the release
        mainline_wait_event.wait()
        mainline_wait_event.clear()

        a_lock.verify_lock(
            exp_q=[
                LockItem(
                    mode=SELockObtainMode.Share,
                    event_flag=True,
                    thread=f5_thread,
                )
            ],
            exp_owner_count=1,
            exp_excl_wait_count=0,
            verify_structures=True,
        )

        # tell f5 to release the lock
        f5_wait_event.set()

        # wait for f5 to tell us the lock is released
        mainline_wait_event.wait()

        a_lock.verify_lock(
            exp_q=[],
            exp_owner_count=0,
            exp_excl_wait_count=0,
            verify_structures=True,
        )

        f4_thread.join()
        f5_thread.join()

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)


########################################################################
# TestSELock class
########################################################################
class TestSELock:
    """Class TestSELock."""

    ####################################################################
    # test_se_lock_timeout
    ####################################################################
    @pytest.mark.parametrize(
        "timeout_arg",
        [0.1, 0.5, 12],
    )
    @pytest.mark.parametrize(
        "use_timeout_arg",
        [True, False],
    )
    @pytest.mark.parametrize(
        "ml_context_arg",
        [
            ContextArg.NoContext,
            ContextArg.ContextExclShare,
            ContextArg.ContextObtain,
        ],
    )
    @pytest.mark.parametrize(
        "f1_context_arg",
        [
            ContextArg.NoContext,
            ContextArg.ContextExclShare,
            ContextArg.ContextObtain,
        ],
    )
    def test_se_lock_timeout(
        self,
        timeout_arg: float,
        use_timeout_arg: int,
        ml_context_arg: ContextArg,
        f1_context_arg: ContextArg,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Method to test se_lock timeout cases.

        Args:
            timeout_arg: number of seconds to use for timeout value
            use_timeout_arg: indicates whether to use timeout
            ml_context_arg: specifies how mainline obtains the lock
            f1_context_arg: specifies how f1 obtains the lock

        """

        def f1(use_timeout_tf: bool, f1_context: ContextArg) -> None:
            """Function to get the lock and wait.

            Args:
                use_timeout_tf: indicates whether to specify timeout
                                  on the lock requests
                f1_context: specifies how f1 obtains the lock

            """
            log_ver.test_msg(log_msg="f1 entered")

            ############################################################
            # Excl mode
            ############################################################
            obtaining_log_msg = f"f1 obtaining excl {f1_context=} {use_timeout_tf=}"
            obtained_log_msg = f"f1 obtained excl {f1_context=} {use_timeout_tf=}"

            f1_esc_thread_name = re.escape(f"{f1_thread.name}")

            if f1_context == ContextArg.NoContext:
                f1_excl_call_seq = (
                    "threading.py::Thread.run:[0-9]+ -> test_se_lock.py::f1:[0-9]+"
                )
            elif f1_context == ContextArg.ContextExclShare:
                f1_excl_call_seq = (
                    "test_se_lock.py::f1:[0-9]+ "
                    "-> se_lock.py::SELockExcl.__enter__:[0-9]+"
                )
            else:
                f1_excl_call_seq = (
                    "test_se_lock.py::f1:[0-9]+ "
                    "-> se_lock.py::SELockObtain.__enter__:[0-9]+"
                )

            f1_excl_obtain_pattern = (
                "SELock exclusive obtain request granted immediate exclusive "
                f"control to thread {f1_esc_thread_name}, "
                f"call sequence: {f1_excl_call_seq}"
            )

            log_ver.add_pattern(pattern=f1_excl_obtain_pattern)

            if f1_context == ContextArg.NoContext:
                f1_excl_release_seq = (
                    "threading.py::Thread.run:[0-9]+ -> test_se_lock.py::f1:[0-9]+"
                )
            elif f1_context == ContextArg.ContextExclShare:
                f1_excl_release_seq = (
                    "test_se_lock.py::f1:[0-9]+ "
                    "-> se_lock.py::SELockExcl.__exit__:[0-9]+"
                )
            else:
                f1_excl_release_seq = (
                    "test_se_lock.py::f1:[0-9]+ "
                    "-> se_lock.py::SELockObtain.__exit__:[0-9]+"
                )

            f1_excl_release_pattern = (
                f"SELock release request removed exclusive control for thread "
                f"{f1_esc_thread_name}, "
                f"call sequence: {f1_excl_release_seq}"
            )
            log_ver.add_pattern(pattern=f1_excl_release_pattern)

            if f1_context == ContextArg.NoContext:
                if use_timeout_tf:
                    log_ver.test_msg(log_msg=obtaining_log_msg)
                    a_lock.obtain_excl(timeout=timeout_arg)
                    log_ver.test_msg(log_msg=obtained_log_msg)
                else:
                    log_ver.test_msg(log_msg=obtaining_log_msg)
                    a_lock.obtain_excl()
                    log_ver.test_msg(log_msg=obtained_log_msg)

                msgs.queue_msg("alpha")
                msgs.get_msg("beta", timeout=msgs_get_to)

                a_lock.release()

            elif f1_context == ContextArg.ContextExclShare:
                if use_timeout_tf:
                    log_ver.test_msg(log_msg=obtaining_log_msg)
                    with SELockExcl(a_lock, timeout=timeout_arg):
                        log_ver.test_msg(log_msg=obtained_log_msg)
                        msgs.queue_msg("alpha")
                        msgs.get_msg("beta", timeout=msgs_get_to)
                else:
                    log_ver.test_msg(log_msg=obtaining_log_msg)
                    with SELockExcl(a_lock):
                        log_ver.test_msg(log_msg=obtained_log_msg)
                        msgs.queue_msg("alpha")
                        msgs.get_msg("beta", timeout=msgs_get_to)
            else:
                if use_timeout_tf:
                    log_ver.test_msg(log_msg=obtaining_log_msg)
                    with SELockObtain(
                        a_lock,
                        obtain_mode=SELockObtainMode.Exclusive,
                        timeout=timeout_arg,
                    ):
                        log_ver.test_msg(log_msg=obtained_log_msg)
                        msgs.queue_msg("alpha")
                        msgs.get_msg("beta", timeout=msgs_get_to)
                else:
                    log_ver.test_msg(log_msg=obtaining_log_msg)
                    with SELockObtain(a_lock, obtain_mode=SELockObtainMode.Exclusive):
                        log_ver.test_msg(log_msg=obtained_log_msg)
                        msgs.queue_msg("alpha")
                        msgs.get_msg("beta", timeout=msgs_get_to)

            ############################################################
            # Share mode
            ############################################################
            obtaining_log_msg = f"f1 obtaining share {f1_context=} {use_timeout_tf=}"
            obtained_log_msg = f"f1 obtained share {f1_context=} {use_timeout_tf=}"

            if f1_context == ContextArg.NoContext:
                f1_share_call_seq = (
                    "threading.py::Thread.run:[0-9]+ -> test_se_lock.py::f1:[0-9]+"
                )
            elif f1_context == ContextArg.ContextExclShare:
                f1_share_call_seq = (
                    "test_se_lock.py::f1:[0-9]+ "
                    "-> se_lock.py::SELockShare.__enter__:[0-9]+"
                )
            else:
                f1_share_call_seq = (
                    "test_se_lock.py::f1:[0-9]+ "
                    "-> se_lock.py::SELockObtain.__enter__:[0-9]+"
                )

            f1_share_obtain_pattern = (
                "SELock share obtain request granted immediate shared "
                f"control to thread {f1_esc_thread_name}, "
                f"call sequence: {f1_share_call_seq}"
            )

            log_ver.add_pattern(pattern=f1_share_obtain_pattern)

            if f1_context == ContextArg.NoContext:
                f1_share_release_seq = (
                    "threading.py::Thread.run:[0-9]+ -> test_se_lock.py::f1:[0-9]+"
                )
            elif f1_context == ContextArg.ContextExclShare:
                f1_share_release_seq = (
                    "test_se_lock.py::f1:[0-9]+ "
                    "-> se_lock.py::SELockShare.__exit__:[0-9]+"
                )
            else:
                f1_share_release_seq = (
                    "test_se_lock.py::f1:[0-9]+ "
                    "-> se_lock.py::SELockObtain.__exit__:[0-9]+"
                )

            f1_share_release_pattern = (
                f"SELock release request removed shared control for thread "
                f"{f1_esc_thread_name}, "
                f"call sequence: {f1_share_release_seq}"
            )
            log_ver.add_pattern(pattern=f1_share_release_pattern)

            if f1_context == ContextArg.NoContext:
                if use_timeout_tf:
                    log_ver.test_msg(log_msg=obtaining_log_msg)
                    a_lock.obtain_share(timeout=timeout_arg)
                    log_ver.test_msg(log_msg=obtained_log_msg)
                else:
                    log_ver.test_msg(log_msg=obtaining_log_msg)
                    a_lock.obtain_share()
                    log_ver.test_msg(log_msg=obtained_log_msg)

                msgs.queue_msg("alpha")
                msgs.get_msg("beta", timeout=msgs_get_to)

                a_lock.release()  # @sbt why no release?

            elif f1_context == ContextArg.ContextExclShare:
                if use_timeout_tf:
                    log_ver.test_msg(log_msg=obtaining_log_msg)
                    with SELockShare(a_lock, timeout=timeout_arg):
                        log_ver.test_msg(log_msg=obtained_log_msg)
                        msgs.queue_msg("alpha")
                        msgs.get_msg("beta", timeout=msgs_get_to)
                else:
                    log_ver.test_msg(log_msg=obtaining_log_msg)
                    with SELockShare(a_lock):
                        log_ver.test_msg(log_msg=obtained_log_msg)
                        msgs.queue_msg("alpha")
                        msgs.get_msg("beta", timeout=msgs_get_to)
            else:
                if use_timeout_tf:
                    log_ver.test_msg(log_msg=obtaining_log_msg)
                    with SELockObtain(
                        a_lock, obtain_mode=SELockObtainMode.Share, timeout=timeout_arg
                    ):
                        log_ver.test_msg(log_msg=obtained_log_msg)
                        msgs.queue_msg("alpha")
                        msgs.get_msg("beta", timeout=msgs_get_to)
                else:
                    log_ver.test_msg(log_msg=obtaining_log_msg)
                    with SELockObtain(a_lock, obtain_mode=SELockObtainMode.Share):
                        log_ver.test_msg(log_msg=obtained_log_msg)
                        msgs.queue_msg("alpha")
                        msgs.get_msg("beta", timeout=msgs_get_to)

            log_ver.test_msg(log_msg="f1 exiting")

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_locking.se_lock")

        log_ver.test_msg(log_msg="mainline entered")

        msgs = Msgs()
        stop_watch = StopWatch()

        a_lock = SELock()

        to_low = timeout_arg
        to_high = timeout_arg * 1.3

        msgs_get_to = timeout_arg * 4 * 2

        ml_thread = threading.current_thread()

        f1_thread = threading.Thread(target=f1, args=(use_timeout_arg, f1_context_arg))
        f1_thread.start()

        f1_thread_name = re.escape(f"{f1_thread.name}")

        log_ver.test_msg(log_msg="mainline about to wait 1")
        msgs.get_msg("alpha")

        ################################################################
        # excl 1
        ################################################################
        log_ver.test_msg(log_msg="mainline about to request excl 1")

        ml_esc_thread_name = re.escape(f"{ml_thread.name}")

        if ml_context_arg == ContextArg.NoContext:
            ml_excl_call_seq = (
                "python.py::pytest_pyfunc_call:[0-9]+ "
                "-> test_se_lock.py::TestSELock.test_se_lock_timeout:[0-9]+"
            )
        elif ml_context_arg == ContextArg.ContextExclShare:
            ml_excl_call_seq = (
                "test_se_lock.py::TestSELock.test_se_lock_timeout:[0-9]+ "
                "-> se_lock.py::SELockExcl.__enter__:[0-9]+"
            )
        else:
            ml_excl_call_seq = (
                "test_se_lock.py::TestSELock.test_se_lock_timeout:[0-9]+ "
                "-> se_lock.py::SELockObtain.__enter__:[0-9]+"
            )

        ml_excl_wait_pattern = (
            f"SELock exclusive obtain request for thread {ml_esc_thread_name} "
            f"waiting for SELock, timeout={timeout_arg}, "
            f"call sequence: {ml_excl_call_seq}"
        )
        log_ver.add_pattern(pattern=ml_excl_wait_pattern)

        ml_excl_timeout_error_pattern = (
            f"SELock exclusive obtain request for thread {ml_esc_thread_name} "
            "raising SELockObtainTimeout because the thread has timed out "
            "waiting for the current owner thread "
            f"{f1_thread_name} to release the lock. "
            f"Request call sequence: {ml_excl_call_seq}"
        )
        log_ver.add_pattern(pattern=ml_excl_timeout_error_pattern, level=logging.ERROR)

        stop_watch.start_clock(clock_iter=1)
        with pytest.raises(SELockObtainTimeout, match=ml_excl_timeout_error_pattern):
            if ml_context_arg == ContextArg.NoContext:
                a_lock.obtain_excl(timeout=timeout_arg)
            elif ml_context_arg == ContextArg.ContextExclShare:
                with SELockExcl(a_lock, timeout=timeout_arg):
                    pass
            else:
                with SELockObtain(
                    a_lock, obtain_mode=SELockObtainMode.Exclusive, timeout=timeout_arg
                ):
                    pass

        assert to_low <= stop_watch.duration() <= to_high

        ################################################################
        # share 1
        ################################################################
        log_ver.test_msg(log_msg="mainline about to request share 1")

        if ml_context_arg == ContextArg.NoContext:
            ml_share_call_seq = (
                "python.py::pytest_pyfunc_call:[0-9]+ -> "
                "test_se_lock.py::TestSELock.test_se_lock_timeout:[0-9]+"
            )
        elif ml_context_arg == ContextArg.ContextExclShare:
            ml_share_call_seq = (
                "test_se_lock.py::TestSELock.test_se_lock_timeout:[0-9]+ "
                "-> se_lock.py::SELockShare.__enter__:[0-9]+"
            )
        else:
            ml_share_call_seq = (
                "test_se_lock.py::TestSELock.test_se_lock_timeout:[0-9]+ "
                "-> se_lock.py::SELockObtain.__enter__:[0-9]+"
            )

        ml_share_wait_pattern = (
            f"SELock share obtain request for thread {ml_esc_thread_name} "
            f"waiting for SELock, timeout={timeout_arg}, "
            f"call sequence: {ml_share_call_seq}"
        )
        log_ver.add_pattern(pattern=ml_share_wait_pattern)

        ml_share_timeout_error_pattern = (
            f"SELock share obtain request for thread {ml_esc_thread_name} "
            "raising SELockObtainTimeout because the thread has timed out "
            "waiting for the current owner thread "
            f"{f1_thread_name} to release the lock. "
            f"Request call sequence: {ml_share_call_seq}"
        )
        log_ver.add_pattern(pattern=ml_share_timeout_error_pattern, level=logging.ERROR)

        stop_watch.start_clock(clock_iter=2)
        with pytest.raises(SELockObtainTimeout, match=ml_share_timeout_error_pattern):
            if ml_context_arg == ContextArg.NoContext:
                a_lock.obtain_share(timeout=timeout_arg)
            elif ml_context_arg == ContextArg.ContextExclShare:
                with SELockShare(a_lock, timeout=timeout_arg):
                    pass
            else:
                with SELockObtain(
                    a_lock, obtain_mode=SELockObtainMode.Share, timeout=timeout_arg
                ):
                    pass
        assert to_low <= stop_watch.duration() <= to_high

        ################################################################
        # excl 2
        ################################################################
        log_ver.test_msg(log_msg="mainline about to request excl 2")

        log_ver.add_pattern(pattern=ml_excl_wait_pattern)
        log_ver.add_pattern(pattern=ml_excl_timeout_error_pattern, level=logging.ERROR)

        stop_watch.start_clock(clock_iter=3)
        with pytest.raises(SELockObtainTimeout, match=ml_excl_timeout_error_pattern):
            if ml_context_arg == ContextArg.NoContext:
                a_lock.obtain_excl(timeout=timeout_arg)
            elif ml_context_arg == ContextArg.ContextExclShare:
                with SELockExcl(a_lock, timeout=timeout_arg):
                    pass
            else:
                with SELockObtain(
                    a_lock, obtain_mode=SELockObtainMode.Exclusive, timeout=timeout_arg
                ):
                    pass
        assert to_low <= stop_watch.duration() <= to_high

        ################################################################
        # share 2
        ################################################################
        log_ver.test_msg(log_msg="mainline about to request share 2")

        log_ver.add_pattern(pattern=ml_share_wait_pattern)
        log_ver.add_pattern(pattern=ml_share_timeout_error_pattern, level=logging.ERROR)

        stop_watch.start_clock(clock_iter=4)
        with pytest.raises(SELockObtainTimeout, match=ml_share_timeout_error_pattern):
            if ml_context_arg == ContextArg.NoContext:
                a_lock.obtain_share(timeout=timeout_arg)
            elif ml_context_arg == ContextArg.ContextExclShare:
                with SELockShare(a_lock, timeout=timeout_arg):
                    pass
            else:
                with SELockObtain(
                    a_lock, obtain_mode=SELockObtainMode.Share, timeout=timeout_arg
                ):
                    pass
        assert to_low <= stop_watch.duration() <= to_high

        msgs.queue_msg("beta")

        log_ver.test_msg(log_msg="mainline about to wait 2")
        msgs.get_msg("alpha")

        ################################################################
        # excl 3
        ################################################################
        log_ver.test_msg(log_msg="mainline about to request excl 3")

        log_ver.add_pattern(pattern=ml_excl_wait_pattern)
        log_ver.add_pattern(pattern=ml_excl_timeout_error_pattern, level=logging.ERROR)

        stop_watch.start_clock(clock_iter=5)
        with pytest.raises(SELockObtainTimeout, match=ml_excl_timeout_error_pattern):
            if ml_context_arg == ContextArg.NoContext:
                a_lock.obtain_excl(timeout=timeout_arg)
            elif ml_context_arg == ContextArg.ContextExclShare:
                with SELockExcl(a_lock, timeout=timeout_arg):
                    pass
            else:
                with SELockObtain(
                    a_lock, obtain_mode=SELockObtainMode.Exclusive, timeout=timeout_arg
                ):
                    pass
        assert to_low <= stop_watch.duration() <= to_high

        ################################################################
        # share 3
        ################################################################
        log_ver.test_msg(log_msg="mainline about to request share 3")

        ml_share_obtain_pattern = (
            "SELock share obtain request granted immediate shared "
            f"control to thread {ml_esc_thread_name}, "
            f"call sequence: {ml_share_call_seq}"
        )

        log_ver.add_pattern(pattern=ml_share_obtain_pattern)

        if ml_context_arg == ContextArg.NoContext:
            ml_share_exit_seq = (
                "python.py::pytest_pyfunc_call:[0-9]+ -> "
                "test_se_lock.py::TestSELock.test_se_lock_timeout:[0-9]+"
            )
        elif ml_context_arg == ContextArg.ContextExclShare:
            ml_share_exit_seq = (
                "test_se_lock.py::TestSELock.test_se_lock_timeout:[0-9]+ "
                "-> se_lock.py::SELockShare.__exit__:[0-9]+"
            )
        else:
            ml_share_exit_seq = (
                "test_se_lock.py::TestSELock.test_se_lock_timeout:[0-9]+ "
                "-> se_lock.py::SELockObtain.__exit__:[0-9]+"
            )

        ml_share_release_pattern = (
            f"SELock release request removed shared control for thread "
            f"{ml_esc_thread_name}, "
            f"call sequence: {ml_share_exit_seq}"
        )
        log_ver.add_pattern(pattern=ml_share_release_pattern)

        if ml_context_arg == ContextArg.NoContext:
            a_lock.obtain_share(timeout=timeout_arg)
            a_lock.release()
        elif ml_context_arg == ContextArg.ContextExclShare:
            with SELockShare(a_lock, timeout=timeout_arg):
                pass
        else:
            with SELockObtain(
                a_lock, obtain_mode=SELockObtainMode.Share, timeout=timeout_arg
            ):
                pass

        ################################################################
        # excl 4
        ################################################################
        log_ver.test_msg(log_msg="mainline about to request excl 4")

        log_ver.add_pattern(pattern=ml_excl_wait_pattern)
        log_ver.add_pattern(pattern=ml_excl_timeout_error_pattern, level=logging.ERROR)

        stop_watch.start_clock(clock_iter=6)
        with pytest.raises(SELockObtainTimeout, match=ml_excl_timeout_error_pattern):
            if ml_context_arg == ContextArg.NoContext:
                a_lock.obtain_excl(timeout=timeout_arg)
            elif ml_context_arg == ContextArg.ContextExclShare:
                with SELockExcl(a_lock, timeout=timeout_arg):
                    pass
            else:
                with SELockObtain(
                    a_lock, obtain_mode=SELockObtainMode.Exclusive, timeout=timeout_arg
                ):
                    pass
        assert to_low <= stop_watch.duration() <= to_high

        ################################################################
        # share 4
        ################################################################
        log_ver.test_msg(log_msg="mainline about to request share 4")

        log_ver.add_pattern(pattern=ml_share_obtain_pattern)
        log_ver.add_pattern(pattern=ml_share_release_pattern)

        if ml_context_arg == ContextArg.NoContext:
            a_lock.obtain_share(timeout=timeout_arg)
            a_lock.release()
        elif ml_context_arg == ContextArg.ContextExclShare:
            with SELockShare(a_lock, timeout=timeout_arg):
                pass
        else:
            with SELockObtain(
                a_lock, obtain_mode=SELockObtainMode.Share, timeout=timeout_arg
            ):
                pass

        msgs.queue_msg("beta")
        f1_thread.join()
        log_ver.test_msg(log_msg="mainline exiting")

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_se_lock_combos
    ####################################################################
    @pytest.mark.parametrize("num_share_requests1_arg", [0, 1, 2, 3])
    @pytest.mark.parametrize("num_share_requests2_arg", [0, 1, 2, 3])
    @pytest.mark.parametrize("num_excl_requests1_arg", [0, 1, 2, 3])
    @pytest.mark.parametrize("num_excl_requests2_arg", [0, 1, 2, 3])
    @pytest.mark.parametrize("release_position_arg", [0, 1, 2])
    @pytest.mark.parametrize("use_context_arg", [0, 1, 2, 3])
    def test_se_lock_combos(
        self,
        num_share_requests1_arg: int,
        num_excl_requests1_arg: int,
        num_share_requests2_arg: int,
        num_excl_requests2_arg: int,
        release_position_arg: int,
        use_context_arg: int,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Method to test se_lock excl and share combos.

        The following section tests various scenarios of shared and
        exclusive locking.

        We will try combinations of shared and exclusive obtains and
        verify that the order in requests is maintained.

        Scenario:
           1) obtain 0 to 3 shared - verify
           2) obtain 0 to 3 exclusive - verify
           3) obtain 0 to 3 shared - verify
           4) obtain 0 to 3 exclusive - verify

        Args:
            num_share_requests1_arg: number of first share requests
            num_excl_requests1_arg: number of first excl requests
            num_share_requests2_arg: number of second share requests
            num_excl_requests2_arg: number of second excl requests
            release_position_arg: indicates the position among the lock
                                    owners that will release the lock
            use_context_arg: indicate whether to use context manager
                               to request the lock

        """
        num_groups = 4

        def f1(
            a_event: threading.Event,
            mode: SELock._Mode,
            req_num: int,
            use_context: ContextArg,
            f1_release_grant_list: list["ReleaseGrant"],
        ) -> None:
            """Function to get the lock and wait.

            Args:
                a_event: instance of threading.Event
                mode: shared or exclusive
                req_num: request number assigned
                use_context: indicate whether to use context manager
                    lock obtain or to make the call directly

            """

            def f1_verify() -> None:
                """Verify the thread item contains expected info."""
                for f1_item in thread_event_list:
                    if f1_item.req_num == req_num:
                        assert f1_item.thread is threading.current_thread()
                        assert f1_item.mode == mode
                        assert f1_item.lock_obtained is False
                        f1_item.lock_obtained = True
                        break
                a_lock.verify_lock()

            if mode == SELock._Mode.SHARE:
                req_type_insert = "share"
                grant_type_insert = "shared"
                obtain_seq_insert = "Share"
            else:
                req_type_insert = "exclusive"
                grant_type_insert = "exclusive"
                obtain_seq_insert = "Excl"

            f1_esc_thread_name = re.escape(f"{threading.current_thread().name}")

            if use_context == ContextArg.NoContext:
                f1_obtain_call_seq = (
                    "threading.py::Thread.run:[0-9]+ -> test_se_lock.py::f1:[0-9]+"
                )
                f1_release_call_seq = f1_obtain_call_seq
            elif use_context == ContextArg.ContextExclShare:
                f1_obtain_call_seq = (
                    "test_se_lock.py::f1:[0-9]+ "
                    f"-> se_lock.py::SELock{obtain_seq_insert}.__enter__:[0-9]+"
                )
                f1_release_call_seq = (
                    "test_se_lock.py::f1:[0-9]+ "
                    f"-> se_lock.py::SELock{obtain_seq_insert}.__exit__:[0-9]+"
                )
            else:
                f1_obtain_call_seq = (
                    "test_se_lock.py::f1:[0-9]+ "
                    "-> se_lock.py::SELockObtain.__enter__:[0-9]+"
                )
                f1_release_call_seq = (
                    "test_se_lock.py::f1:[0-9]+ "
                    "-> se_lock.py::SELockObtain.__exit__:[0-9]+"
                )

            if req_num < num_initial_owners:
                f1_obtain_pattern = (
                    f"SELock {req_type_insert} obtain request granted immediate "
                    f"{grant_type_insert} control to thread {f1_esc_thread_name}, "
                    f"call sequence: {f1_obtain_call_seq}"
                )
            else:
                f1_obtain_pattern = (
                    f"SELock {req_type_insert} obtain request for thread "
                    f"{f1_esc_thread_name} waiting for SELock, timeout=None, "
                    f"call sequence: {f1_obtain_call_seq}"
                )

            log_ver.add_pattern(pattern=f1_obtain_pattern)

            f1_release_pattern = (
                f"SELock release request removed {grant_type_insert} control for "
                f"thread {f1_esc_thread_name}, "
                f"call sequence: {f1_release_call_seq}"
            )
            log_ver.add_pattern(pattern=f1_release_pattern)

            ############################################################
            # request the lock
            ############################################################
            if use_context == ContextArg.NoContext:
                if mode == SELock._Mode.SHARE:
                    a_lock.obtain_share()
                else:
                    a_lock.obtain_excl()
                f1_verify()

                a_event.wait()
                a_lock.release()

            elif use_context == ContextArg.ContextExclShare:
                if mode == SELock._Mode.SHARE:
                    with SELockShare(a_lock):
                        f1_verify()
                        a_event.wait()
                else:
                    with SELockExcl(a_lock):
                        f1_verify()
                        a_event.wait()

            else:
                if mode == SELock._Mode.SHARE:
                    with SELockObtain(a_lock, obtain_mode=SELockObtainMode.Share):
                        f1_verify()
                        a_event.wait()
                else:
                    with SELockObtain(a_lock, obtain_mode=SELockObtainMode.Exclusive):
                        f1_verify()
                        a_event.wait()

            for item in f1_release_grant_list:
                if item.mode == SELock._Mode.SHARE:
                    rel_grant_mode = "shared"
                else:
                    rel_grant_mode = "exclusive"

                granted_esc_thread = re.escape(f"{item.thread}")

                f1_release_grant_pattern = (
                    f"SELock release request for thread "
                    f"{f1_esc_thread_name} "
                    f"granted {rel_grant_mode} control to waiting "
                    f"thread {granted_esc_thread}, "
                    f"call sequence: {f1_release_call_seq}"
                )
                log_ver.add_pattern(pattern=f1_release_grant_pattern)

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_locking.se_lock")

        @dataclass
        class ReleaseGrant:
            thread: threading.Thread
            mode: SELock._Mode

        @dataclass
        class ThreadEvent:
            thread: threading.Thread
            event: threading.Event
            mode: SELock._Mode
            req_num: int
            lock_obtained: bool
            release_grant_list: list[ReleaseGrant]

        a_lock = SELock()

        a_lock.verify_lock()

        thread_event_list = []

        request_number = -1
        num_requests_list = [
            num_share_requests1_arg,
            num_excl_requests1_arg,
            num_share_requests2_arg,
            num_excl_requests2_arg,
        ]

        num_initial_owners = 0
        initial_owner_mode: Optional[SELock._Mode] = None
        if num_share_requests1_arg:
            num_initial_owners = num_share_requests1_arg
            initial_owner_mode = SELock._Mode.SHARE
            if num_excl_requests1_arg == 0:
                num_initial_owners += num_share_requests2_arg
        elif num_excl_requests1_arg:
            num_initial_owners = 1
            initial_owner_mode = SELock._Mode.EXCL
        elif num_share_requests2_arg:
            num_initial_owners = num_share_requests2_arg
            initial_owner_mode = SELock._Mode.SHARE
        elif num_excl_requests2_arg:
            num_initial_owners = 1
            initial_owner_mode = SELock._Mode.EXCL

        for shr_excl in range(num_groups):
            num_requests = num_requests_list[shr_excl]
            for idx in range(num_requests):
                request_number += 1
                a_event1 = threading.Event()
                if shr_excl == 0 or shr_excl == 2:
                    req_mode = SELock._Mode.SHARE
                else:
                    req_mode = SELock._Mode.EXCL

                if use_context_arg == 0:
                    use_context = ContextArg.NoContext
                elif use_context_arg == 1:
                    use_context = ContextArg.ContextExclShare
                elif use_context_arg == 2:
                    use_context = ContextArg.ContextObtain
                else:
                    if request_number % 3 == 0:
                        use_context = ContextArg.NoContext
                    elif request_number % 3 == 1:
                        use_context = ContextArg.ContextExclShare
                    else:
                        use_context = ContextArg.ContextObtain

                release_grant_list: list[ReleaseGrant] = []

                a_thread = threading.Thread(
                    target=f1,
                    args=(
                        a_event1,
                        req_mode,
                        request_number,
                        use_context,
                        release_grant_list,
                    ),
                )
                # save for verification and release
                thread_event_list.append(
                    ThreadEvent(
                        thread=a_thread,
                        event=a_event1,
                        mode=req_mode,
                        req_num=request_number,
                        lock_obtained=False,
                        release_grant_list=release_grant_list,
                    )
                )

                a_thread.start()

                # make sure the request has been queued
                while (not a_lock.owner_wait_q) or (
                    not a_lock.owner_wait_q[-1].thread is a_thread
                ):
                    time.sleep(0.1)
                # logger.debug(f'shr_excl = {shr_excl}, '
                #              f'idx = {idx}, '
                #              f'num_requests_made = {request_number}, '
                #              f'len(a_lock) = {len(a_lock)}')
                assert len(a_lock) == request_number + 1

                # verify
                assert a_lock.owner_wait_q[-1].thread is a_thread
                assert not a_lock.owner_wait_q[-1].event.is_set()
                a_lock.verify_lock()

        work_shr1 = num_share_requests1_arg
        work_excl1 = num_excl_requests1_arg
        work_shr2 = num_share_requests2_arg
        work_excl2 = num_excl_requests2_arg
        while thread_event_list:
            exp_num_owners = 0
            if work_shr1:
                exp_num_owners = work_shr1
                if work_excl1 == 0:
                    exp_num_owners += work_shr2
            elif work_excl1:
                exp_num_owners = 1
            elif work_shr2:
                exp_num_owners = work_shr2
            elif work_excl2:
                exp_num_owners = 1

            while True:
                exp_num_owners_found = 0
                for idx in range(exp_num_owners):  # wait for next owners
                    if thread_event_list[idx].lock_obtained:
                        exp_num_owners_found += 1
                    else:
                        break
                if exp_num_owners_found == exp_num_owners:
                    break
                time.sleep(0.0001)

            for idx, thread_event in enumerate(thread_event_list):
                assert thread_event.thread == thread_event_list[idx].thread
                assert thread_event.thread == a_lock.owner_wait_q[idx].thread
                assert thread_event.mode == thread_event_list[idx].mode
                assert thread_event.mode == a_lock.owner_wait_q[idx].mode

                if idx + 1 <= num_initial_owners:
                    # we expect the event to not have been posted
                    assert not a_lock.owner_wait_q[idx].event.is_set()
                    assert thread_event.mode == initial_owner_mode
                    assert thread_event.lock_obtained is True
                elif idx + 1 <= exp_num_owners:
                    assert a_lock.owner_wait_q[idx].event.is_set()
                    assert thread_event.lock_obtained is True
                else:
                    assert not a_lock.owner_wait_q[idx].event.is_set()
                    assert thread_event.lock_obtained is False

            release_position = min(release_position_arg, exp_num_owners - 1)

            if release_position == 0 and 1 < len(thread_event_list):
                if thread_event_list[1].mode == SELock._Mode.EXCL:
                    thread_event_list[release_position].release_grant_list.append(
                        ReleaseGrant(
                            thread=thread_event_list[1].thread, mode=SELock._Mode.EXCL
                        )
                    )
                else:
                    if thread_event_list[0].mode == SELock._Mode.EXCL:
                        for rel_idx in range(1, len(thread_event_list)):
                            if thread_event_list[rel_idx].mode == SELock._Mode.EXCL:
                                break
                            thread_event_list[
                                release_position
                            ].release_grant_list.append(
                                ReleaseGrant(
                                    thread=thread_event_list[rel_idx].thread,
                                    mode=SELock._Mode.SHARE,
                                )
                            )

            thread_event = thread_event_list.pop(release_position)

            thread_event.event.set()  # tell owner to release and return
            thread_event.thread.join()  # ensure release is complete
            num_initial_owners -= 1
            request_number -= 1
            if work_shr1:
                work_shr1 -= 1
            elif work_excl1:
                work_excl1 -= 1
            elif work_shr2:
                work_shr2 -= 1
            elif work_excl2:
                work_excl2 -= 1

            assert len(a_lock) == request_number + 1

        a_lock.verify_lock()

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)

    ####################################################################
    # test_se_lock_multi_thread_combos
    ####################################################################
    lock_requests1 = it.product(lock_request_list, repeat=4)
    lock_requests2 = it.product(lock_request_list, repeat=3)
    lock_requests3 = it.product(lock_request_list, repeat=2)

    @pytest.mark.parametrize("app1_requests_arg", lock_requests1)
    @pytest.mark.parametrize("app2_requests_arg", lock_requests2)
    @pytest.mark.parametrize("app3_requests_arg", lock_requests3)
    def test_se_lock_multi_thread_combos(
        self,
        app1_requests_arg: tuple[SELock.ReqType],
        app2_requests_arg: tuple[SELock.ReqType],
        app3_requests_arg: tuple[SELock.ReqType],
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Method to test multi threaded se_lock excl and share combos.

        Args:
            app1_requests_arg: list of lock requests for f1
            app2_requests_arg: list of lock requests for f2

        """

        def app_thread(
            request_list: tuple[SELock.ReqType],
        ) -> None:
            """Function to get the lock and wait.

            Args:
                request_list: list of lock requests for f_rtn

            """
            thread_esc_name = re.escape(f"{threading.current_thread().name}")
            f1_call_seq = (
                "threading.py::Thread.run:[0-9]+ -> test_se_lock.py::app_thread:[0-9]+"
            )
            ml_event0.set()
            ml_event1.wait()

            lock_owner_count = 0
            for idx, request in enumerate(request_list):
                logger.debug(f"f1 doing request {idx}: {request}")
                if request == SELock.ReqType.Exclusive:
                    if lock_owner_count == 0:
                        a_lock.obtain_excl()
                        lock_owner_count = -1
                    else:
                        f1_error_msg = (
                            f"{request} for thread {thread_esc_name} "
                            "raising SELockAlreadyOwnedError because the requestor "
                            "already owns the lock. "
                            f"Request call sequence: {f1_call_seq}"
                        )
                        with pytest.raises(SELockAlreadyOwnedError, match=f1_error_msg):
                            a_lock.obtain_excl()

                elif request == SELock.ReqType.ExclusiveRecursive:
                    if lock_owner_count <= 0:
                        a_lock.obtain_excl_recursive()
                        lock_owner_count -= 1
                    else:
                        f1_error_msg = (
                            f"{request} for thread {thread_esc_name} "
                            "raising SELockAlreadyOwnedError because the requestor "
                            "already owns the lock. "
                            f"Request call sequence: {f1_call_seq}"
                        )
                        with pytest.raises(SELockAlreadyOwnedError, match=f1_error_msg):
                            a_lock.obtain_excl_recursive()

                elif request == SELock.ReqType.Share:
                    if lock_owner_count == 0:
                        a_lock.obtain_share()
                        lock_owner_count = 1
                    else:
                        f1_error_msg = (
                            f"{request} for thread {thread_esc_name} "
                            "raising SELockAlreadyOwnedError because the requestor "
                            "already owns the lock. "
                            f"Request call sequence: {f1_call_seq}"
                        )
                        with pytest.raises(SELockAlreadyOwnedError, match=f1_error_msg):
                            a_lock.obtain_share()

                elif request == SELock.ReqType.Release:
                    if lock_owner_count == 1:
                        a_lock.release()
                        lock_owner_count = 0
                    elif lock_owner_count < 0:
                        a_lock.release()
                        lock_owner_count += 1
                    else:
                        f1_error_msg = (
                            f"{request} for thread {thread_esc_name} raising "
                            "AttemptedReleaseOfUnownedLock because an entry on the "
                            "owner-waiter queue was not found for that thread. "
                            f"Request call sequence: {f1_call_seq}"
                        )
                        with pytest.raises(
                            AttemptedReleaseOfUnownedLock, match=f1_error_msg
                        ):
                            a_lock.release()

                else:
                    raise InvalidRequestType(f"request {request} not valid")

            while lock_owner_count:
                a_lock.release()
                if lock_owner_count == 1:
                    lock_owner_count = 0
                else:
                    lock_owner_count += 1

        ################################################################
        # mainline
        ################################################################
        a_lock = SELock()

        ml_event0 = threading.Event()
        ml_event1 = threading.Event()

        f1_thread = threading.Thread(target=app_thread, args=(app1_requests_arg,))
        f1_thread.start()
        ml_event0.wait()
        ml_event0.clear()

        f2_thread = threading.Thread(target=app_thread, args=(app2_requests_arg,))
        f2_thread.start()
        ml_event0.wait()
        ml_event0.clear()

        f3_thread = threading.Thread(target=app_thread, args=(app3_requests_arg,))
        f3_thread.start()
        ml_event0.wait()
        ml_event0.clear()

        ml_event1.set()

        f1_thread.join()
        f2_thread.join()
        f3_thread.join()


########################################################################
# TestSELockDocstrings class
########################################################################
class TestSELockVerify:
    """Class TestSELockVerify."""

    @pytest.mark.parametrize("num_excl_grp1_arg", [0, 1, 2, 3])
    @pytest.mark.parametrize("num_share_grp2_arg", [0, 1, 2, 3])
    @pytest.mark.parametrize("num_excl_grp3_arg", [0, 1, 2, 3])
    @pytest.mark.parametrize("num_share_grp4_arg", [0, 1, 2, 3])
    @pytest.mark.parametrize(
        "timeout_type_arg",
        [TimeoutType.TimeoutNone, TimeoutType.TimeoutFalse, TimeoutType.TimeoutTrue],
    )
    def test_lock_multi_thread_verify(
        self,
        num_excl_grp1_arg: int,
        num_share_grp2_arg: int,
        num_excl_grp3_arg: int,
        num_share_grp4_arg: int,
        timeout_type_arg: TimeoutType,
        caplog: pytest.LogCaptureFixture,
    ) -> None:
        """Method to test multi threaded se_lock excl and share combos.

        Args:
            num_excl_grp1_arg: number exclusive requestors in group 1
            num_share_grp2_arg: number shared requestors in group 2
            num_excl_grp3_arg: number exclusive requestors in group 3
            num_share_grp4_arg: number shared requestors in group 4
            timeout_type_arg: specifies whether to timeout

        """

        @dataclass
        class ThreadEventPair:
            thread: threading.Thread
            event: threading.Event

        @dataclass
        class CountsAndQ:
            exp_q: list[LockItem]
            exp_real_q: list[LockItem]
            thread_event_pairs: list[ThreadEventPair]
            exp_owner_count: int = 0
            exp_real_owner_count: int = 0
            exp_excl_wait_count: int = 0
            exp_real_excl_wait_count: int = 0

        ################################################################
        # app_thread
        ################################################################
        def app_thread(
            req_type: SELockObtainMode,
            app_event: threading.Event,
        ) -> None:
            """Function to get the lock and wait.

            Args:
                req_type: lock request to do
                app_event: event to wait on before releasing lock

            """
            if timeout_type_arg != TimeoutType.TimeoutNone:
                time.sleep(2)

            with SELockObtain(se_lock=a_lock, obtain_mode=req_type):
                app_event.wait()
                if timeout_type_arg != TimeoutType.TimeoutNone:
                    time.sleep(2)

        ################################################################
        # verify_rtn
        ################################################################
        def verify_rtn(
            exp_q: list[LockItem],
            exp_real_q: list[LockItem],
            exp_owner_count: int,
            exp_real_owner_count: int,
            exp_excl_wait_count: int,
            exp_real_excl_wait_count: int,
        ):
            if timeout_type_arg == TimeoutType.TimeoutNone:
                a_lock.verify_lock(
                    exp_q=exp_q,
                    exp_owner_count=exp_owner_count,
                    exp_excl_wait_count=exp_excl_wait_count,
                    verify_structures=True,
                )
            elif timeout_type_arg == TimeoutType.TimeoutFalse:
                a_lock.verify_lock(
                    exp_q=exp_q,
                    exp_owner_count=exp_owner_count,
                    exp_excl_wait_count=exp_excl_wait_count,
                    verify_structures=True,
                    timeout=4,
                )
            else:
                ml_error_msg = (
                    re.escape(
                        f"lock_verify raising LockVerifyError. {exp_q=}, "
                        f"lock_info.queue={exp_real_q}, {exp_owner_count=}, "
                        f"lock_info.owner_count={exp_real_owner_count}, "
                        f"{exp_excl_wait_count=}, "
                        f"lock_info.excl_wait_count={exp_real_excl_wait_count}, "
                        f"timeout=1. "
                    )
                    + ml_call_seq
                )
                log_ver.add_pattern(pattern=ml_error_msg, level=logging.ERROR)

                with pytest.raises(LockVerifyError, match=ml_error_msg):
                    a_lock.verify_lock(
                        exp_q=exp_q,
                        exp_owner_count=exp_owner_count,
                        exp_excl_wait_count=exp_excl_wait_count,
                        verify_structures=True,
                        timeout=1,
                    )

        ################################################################
        # get_lock
        ################################################################
        def get_lock(
            gl_counts_and_q: CountsAndQ,
            req_type: SELockObtainMode,
        ):

            a_event = threading.Event()
            a_thread = threading.Thread(target=app_thread, args=(req_type, a_event))
            gl_counts_and_q.thread_event_pairs.append(
                ThreadEventPair(thread=a_thread, event=a_event)
            )

            gl_counts_and_q.exp_real_q = gl_counts_and_q.exp_q.copy()
            gl_counts_and_q.exp_real_owner_count = gl_counts_and_q.exp_owner_count
            gl_counts_and_q.exp_real_excl_wait_count = (
                gl_counts_and_q.exp_excl_wait_count
            )
            gl_counts_and_q.exp_q.append(
                LockItem(
                    mode=req_type,
                    event_flag=False,
                    thread=a_thread,
                )
            )

            esc_thread_name = re.escape(f"{a_thread.name}")
            if req_type == SELockObtainMode.Exclusive:
                if gl_counts_and_q.exp_real_owner_count == 0:
                    gl_counts_and_q.exp_owner_count = -1
                    add_grant_pattern(
                        req_type_insert="exclusive",
                        grant_type_insert="exclusive",
                        esc_thread_name=esc_thread_name,
                    )
                else:
                    gl_counts_and_q.exp_excl_wait_count += 1
                    add_wait_pattern(
                        req_type_insert="exclusive", esc_thread_name=esc_thread_name
                    )
            else:
                if (
                    gl_counts_and_q.exp_real_owner_count >= 0
                    and gl_counts_and_q.exp_real_excl_wait_count == 0
                ):
                    gl_counts_and_q.exp_owner_count += 1
                    add_grant_pattern(
                        req_type_insert="share",
                        grant_type_insert="shared",
                        esc_thread_name=esc_thread_name,
                    )
                else:
                    add_wait_pattern(
                        req_type_insert="share", esc_thread_name=esc_thread_name
                    )

            a_thread.start()

            verify_rtn(
                exp_q=gl_counts_and_q.exp_q,
                exp_real_q=gl_counts_and_q.exp_real_q,
                exp_owner_count=gl_counts_and_q.exp_owner_count,
                exp_real_owner_count=gl_counts_and_q.exp_real_owner_count,
                exp_excl_wait_count=gl_counts_and_q.exp_excl_wait_count,
                exp_real_excl_wait_count=gl_counts_and_q.exp_real_excl_wait_count,
            )

            return gl_counts_and_q

        ################################################################
        # rel_lock
        ################################################################
        def rel_locks(rl_counts_and_q: CountsAndQ):
            for thread_and_event in rl_counts_and_q.thread_event_pairs:
                rl_counts_and_q.exp_real_q = rl_counts_and_q.exp_q.copy()

                rl_counts_and_q.exp_real_owner_count = rl_counts_and_q.exp_owner_count
                rl_counts_and_q.exp_real_excl_wait_count = (
                    rl_counts_and_q.exp_excl_wait_count
                )

                lock_item = rl_counts_and_q.exp_q.pop(0)

                esc_thread_name = re.escape(f"{thread_and_event.thread.name}")

                if lock_item.mode == SELockObtainMode.Exclusive:
                    add_rel_pattern(
                        grant_type_insert="exclusive", esc_thread_name=esc_thread_name
                    )
                    rl_counts_and_q.exp_owner_count = 0
                    for rem_lock_item in rl_counts_and_q.exp_q:
                        granted_esc_thread = re.escape(f"{rem_lock_item.thread.name}")
                        if rem_lock_item.mode == SELockObtainMode.Share:
                            rem_lock_item.event_flag = True
                            rl_counts_and_q.exp_owner_count += 1
                            add_rel_grant_pattern(
                                rel_grant_mode="shared",
                                esc_thread_name=esc_thread_name,
                                granted_esc_thread=granted_esc_thread,
                            )
                        else:
                            if rl_counts_and_q.exp_owner_count == 0:
                                rl_counts_and_q.exp_owner_count = -1
                                rem_lock_item.event_flag = True
                                rl_counts_and_q.exp_excl_wait_count -= 1
                                add_rel_grant_pattern(
                                    rel_grant_mode="exclusive",
                                    esc_thread_name=esc_thread_name,
                                    granted_esc_thread=granted_esc_thread,
                                )
                            break

                else:
                    add_rel_pattern(
                        grant_type_insert="shared", esc_thread_name=esc_thread_name
                    )
                    rl_counts_and_q.exp_owner_count -= 1
                    for rem_lock_item in rl_counts_and_q.exp_q:
                        if rem_lock_item.mode == SELockObtainMode.Exclusive:
                            if rl_counts_and_q.exp_owner_count == 0:
                                rl_counts_and_q.exp_owner_count = -1
                                rem_lock_item.event_flag = True
                                rl_counts_and_q.exp_excl_wait_count -= 1
                                granted_esc_thread = re.escape(
                                    f"{rem_lock_item.thread.name}"
                                )
                                add_rel_grant_pattern(
                                    rel_grant_mode="exclusive",
                                    esc_thread_name=esc_thread_name,
                                    granted_esc_thread=granted_esc_thread,
                                )
                            break

                thread_and_event.event.set()

                verify_rtn(
                    exp_q=rl_counts_and_q.exp_q,
                    exp_real_q=rl_counts_and_q.exp_real_q,
                    exp_owner_count=rl_counts_and_q.exp_owner_count,
                    exp_real_owner_count=rl_counts_and_q.exp_real_owner_count,
                    exp_excl_wait_count=rl_counts_and_q.exp_excl_wait_count,
                    exp_real_excl_wait_count=rl_counts_and_q.exp_real_excl_wait_count,
                )

                thread_and_event.thread.join()

        def add_grant_pattern(
            req_type_insert: str, grant_type_insert: str, esc_thread_name: str
        ):
            log_ver.add_pattern(
                pattern=f"SELock {req_type_insert} obtain request granted immediate "
                f"{grant_type_insert} control to thread {esc_thread_name}, "
                f"call sequence: {obtain_call_seq}"
            )

        def add_wait_pattern(req_type_insert: str, esc_thread_name: str):
            log_ver.add_pattern(
                pattern=f"SELock {req_type_insert} obtain request for thread "
                f"{esc_thread_name} waiting for SELock, timeout=None, "
                f"call sequence: {obtain_call_seq}"
            )

        def add_rel_pattern(grant_type_insert: str, esc_thread_name: str):
            log_ver.add_pattern(
                pattern=f"SELock release request removed {grant_type_insert} control "
                f"for thread {esc_thread_name} call sequence: "
                f"{release_call_seq}"
            )

        def add_rel_grant_pattern(
            rel_grant_mode: str,
            esc_thread_name: str,
            granted_esc_thread: str,
        ):
            log_ver.add_pattern(
                pattern=f"SELock release request for thread {esc_thread_name} "
                f"granted {rel_grant_mode} control to waiting thread "
                f"{granted_esc_thread}, call sequence: {release_call_seq}"
            )

        ################################################################
        # mainline
        ################################################################
        log_ver = LogVer(log_name="scottbrian_locking.se_lock")

        ml_call_seq = (
            "Request call sequence: python.py::pytest_pyfunc_call:[0-9]+ -> "
            "test_se_lock.py::TestSELockVerify.test_lock_multi_thread_verify:[0-9]+"
        )

        obtain_call_seq = (
            "test_se_lock.py::app_thread:[0-9]+ "
            "-> se_lock.py::SELockObtain.__enter__:[0-9]+"
        )
        release_call_seq = (
            "test_se_lock.py::app_thread:[0-9]+ "
            "-> se_lock.py::SELockObtain.__exit__:[0-9]+"
        )

        a_lock = SELock()
        a_lock.verify_lock(
            exp_q=[],
            exp_owner_count=0,
            exp_excl_wait_count=0,
            verify_structures=True,
        )

        ml_counts_and_q = CountsAndQ(exp_q=[], exp_real_q=[], thread_event_pairs=[])
        for idx in range(num_excl_grp1_arg):
            ml_counts_and_q = get_lock(
                gl_counts_and_q=ml_counts_and_q,
                req_type=SELockObtainMode.Exclusive,
            )
        for idx in range(num_share_grp2_arg):
            ml_counts_and_q = get_lock(
                gl_counts_and_q=ml_counts_and_q,
                req_type=SELockObtainMode.Share,
            )
        for idx in range(num_excl_grp3_arg):
            ml_counts_and_q = get_lock(
                gl_counts_and_q=ml_counts_and_q,
                req_type=SELockObtainMode.Share,
            )
        for idx in range(num_share_grp4_arg):
            ml_counts_and_q = get_lock(
                gl_counts_and_q=ml_counts_and_q,
                req_type=SELockObtainMode.Share,
            )

        rel_locks(ml_counts_and_q)

        ################################################################
        # check log results
        ################################################################
        match_results = log_ver.get_match_results(caplog=caplog)
        log_ver.print_match_results(match_results, print_matched=True)
        log_ver.verify_match_results(match_results)


########################################################################
# TestSELockDocstrings class
########################################################################
class TestSELockDocstrings:
    """Class TestSELockDocstrings."""

    ####################################################################
    # test_se_lock_with_example_1
    ####################################################################
    def test_se_lock_with_example_1(self) -> None:
        """Method test_se_lock_with_example_1."""
        flowers("Example of SELock for README:")

        from scottbrian_locking.se_lock import SELock, SELockShare, SELockExcl

        a_lock = SELock()
        # Get lock in exclusive mode
        with SELockExcl(a_lock):  # write to a
            a = 1
            print(f"under exclusive lock, a = {a}")
        # Get lock in shared mode
        with SELockShare(a_lock):  # read a
            print(f"under shared lock, a = {a}")
