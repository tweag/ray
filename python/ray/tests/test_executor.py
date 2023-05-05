import os
import sys
import pytest
from ray.util.concurrent.futures.ray_executor import RayExecutor
import time
import ray
from concurrent.futures import (
    ThreadPoolExecutor,
    ProcessPoolExecutor,
    TimeoutError as ConTimeoutError,
)

@pytest.fixture(autouse=True)
def run_before_and_after_tests():
    yield # this is where the testing happens
    ray.shutdown()

def test_remote_function_runs_on_local_instance():
    with RayExecutor() as ex:
        result = ex.submit(lambda x: x * x, 100).result()
        assert result == 10_000



def test_remote_function_runs_multiple_tasks_on_local_instance():
    with RayExecutor() as ex:
        result0 = ex.submit(lambda x: x * x, 100).result()
        result1 = ex.submit(lambda x: x * x, 100).result()
        assert result0 == result1 == 10_000


def test_order_retained():
    def f(x, y):
        return x * y

    with RayExecutor() as ex:
        r0 = list(ex.map(f, [100, 100, 100], [1, 2, 3]))
    with RayExecutor(max_workers=2) as ex:
        r1 = list(ex.map(f, [100, 100, 100], [1, 2, 3]))
    assert r0 == r1


def test_remote_function_runs_on_local_instance_with_map():
    with RayExecutor() as ex:
        futures_iter = ex.map(lambda x: x * x, [100, 100, 100])
        for result in futures_iter:
            assert result == 10_000


def test_map_zips_iterables():
    def f(x, y):
        return x * y

    with RayExecutor() as ex:
        futures_iter = ex.map(f, [100, 100, 100], [1, 2, 3])
        assert list(futures_iter) == [100, 200, 300]


def test_remote_function_map_using_max_workers():
    with RayExecutor(max_workers=3) as ex:
        assert ex._actor_pool is not None
        assert len(ex._actor_pool._idle_actors) == 3
        time_start = time.monotonic()
        _ = list(ex.map(lambda _: time.sleep(1), range(12)))
        time_end = time.monotonic()
        # we expect about (12*1) / 3 = 4 rounds
        delta = time_end - time_start
        assert delta > 3.0


def test_results_are_accessible_after_shutdown():
    def f(x, y):
        return x * y

    with RayExecutor() as ex:
        r1 = ex.map(f, [100, 100, 100], [1, 2, 3])
    try:
        list(r1)
    except AttributeError:
        pytest.fail("Map results are not accessible after executor shutdown")

def test_actor_pool_results_are_accessible_after_shutdown():
    def f(x, y):
        return x * y

    with RayExecutor(max_workers=2) as ex:
        r1 = ex.map(f, [100, 100, 100], [1, 2, 3])
    try:
        list(r1)
    except AttributeError:
        pytest.fail("Map results are not accessible after executor shutdown")

def test_changing_n_workers_without_shutdown():
    n = 3
    with RayExecutor(max_workers=n) as ex:
        assert ex._actor_pool is not None
        assert len(ex._actor_pool._idle_actors) == n
        time_start = time.monotonic()
        _ = list(ex.map(lambda _: time.sleep(1), range(12)))
        time_end = time.monotonic()
        # we expect about (12*1) / 3 = 4 rounds
        delta = time_end - time_start
        assert delta > 3.0
    n = 6
    with RayExecutor(max_workers=n) as ex:
        assert ex._actor_pool is not None
        assert len(ex._actor_pool._idle_actors) == n
        time_start = time.monotonic()
        _ = list(ex.map(lambda _: time.sleep(1), range(12)))
        time_end = time.monotonic()
        # we expect about (12*1) / 3 = 4 rounds
        delta = time_end - time_start
        assert delta < 3.0


def test_remote_function_max_workers_same_result():
    with RayExecutor() as ex:
        f0 = list(ex.map(lambda x: x * x, range(12)))
    with RayExecutor(max_workers=1) as ex:
        f1 = list(ex.map(lambda x: x * x, range(12)))
    with RayExecutor(max_workers=3) as ex:
        f3 = list(ex.map(lambda x: x * x, range(12)))
    assert f0 == f1 == f3


def test_remote_function_runs_on_specified_instance(call_ray_start):
    with RayExecutor(address=call_ray_start) as ex:
        result = ex.submit(lambda x: x * x, 100).result()
        assert result == 10_000
        assert ex._context.address_info["address"] == call_ray_start


def test_remote_function_runs_on_specified_instance_with_map(call_ray_start):
    with RayExecutor(address=call_ray_start) as ex:
        futures_iter = ex.map(lambda x: x * x, [100, 100, 100])
        for result in futures_iter:
            assert result == 10_000
        assert ex._context.address_info["address"] == call_ray_start


def test_map_times_out():
    def f(x):
        time.sleep(2)
        return x

    with RayExecutor() as ex:
        with pytest.raises(ConTimeoutError):
            i1 = ex.map(f, [1, 2, 3], timeout=1)
            for _ in i1:
                pass


def test_map_times_out_with_max_workers():
    def f(x):
        time.sleep(2)
        return x

    with RayExecutor(max_workers=2) as ex:
        with pytest.raises(ConTimeoutError):
            i1 = ex.map(f, [1, 2, 3], timeout=1)
            for _ in i1:
                pass


def test_remote_function_runs_multiple_tasks_using_max_workers():
    with RayExecutor(max_workers=2) as ex:
        result0 = ex.submit(lambda x: x * x, 100).result()
        result1 = ex.submit(lambda x: x * x, 100).result()
        assert result0 == result1 == 10_000


def test_cannot_submit_after_shutdown():
    ex = RayExecutor(shutdown_ray=True)
    ex.submit(lambda: True).result()
    ex.shutdown()
    with pytest.raises(RuntimeError):
        ex.submit(lambda: True).result()


def test_can_submit_after_shutdown():
    ex = RayExecutor(shutdown_ray=False)
    ex.submit(lambda: True).result()
    ex.shutdown()
    try:
        ex.submit(lambda: True).result()
    except RuntimeError:
        assert (
            False
        ), "Could not submit after calling shutdown() with shutdown_ray=False"
    ex._shutdown_ray = True
    ex.shutdown()


def test_cannot_map_after_shutdown():
    ex = RayExecutor(shutdown_ray=True)
    ex.submit(lambda: True).result()
    ex.shutdown()
    with pytest.raises(RuntimeError):
        ex.submit(lambda: True).result()


def test_pending_task_is_cancelled_after_shutdown():
    ex = RayExecutor(shutdown_ray=True)
    f = ex.submit(lambda: True)
    assert f._state == "PENDING"
    ex.shutdown(cancel_futures=True)
    assert f.cancelled()


def test_running_task_finishes_after_shutdown():
    ex = RayExecutor(shutdown_ray=True)
    f = ex.submit(lambda: True)
    assert f._state == "PENDING"
    f.set_running_or_notify_cancel()
    assert f.running()
    ex.shutdown(cancel_futures=True)
    assert f._state == "FINISHED"


def test_mixed_task_states_handled_by_shutdown():
    ex = RayExecutor(shutdown_ray=True)
    f0 = ex.submit(lambda: True)
    f1 = ex.submit(lambda: True)
    assert f0._state == "PENDING"
    assert f1._state == "PENDING"
    f0.set_running_or_notify_cancel()
    ex.shutdown(cancel_futures=True)
    assert f0._state == "FINISHED"
    assert f1.cancelled()


def test_with_syntax_invokes_shutdown():
    with RayExecutor(shutdown_ray=True) as ex:
        pass
    assert ex._shutdown_lock


# ----------------------------------------------------------------------------------------------------
# ThreadPool/ProcessPool comparison
# ----------------------------------------------------------------------------------------------------

# ProcessPoolExecutor uses pickle which can only serialize top-level functions
def f_process1(x):
    return len([i for i in range(x) if i % 2 == 0])


def test_conformity_with_processpool():
    def f_process0(x):
        return len([i for i in range(x) if i % 2 == 0])

    assert f_process0.__code__.co_code == f_process1.__code__.co_code

    with RayExecutor() as ex:
        ray_result = ex.submit(f_process0, 100).result()
    with ProcessPoolExecutor() as ppe:
        ppe_result = ppe.submit(f_process1, 100).result()
    assert type(ray_result) == type(ppe_result)
    assert ray_result == ppe_result


def test_conformity_with_processpool_map():
    def f_process0(x):
        return len([i for i in range(x) if i % 2 == 0])

    assert f_process0.__code__.co_code == f_process1.__code__.co_code

    with RayExecutor() as ex:
        ray_iter = ex.map(f_process0, range(10))
        ray_result = list(ray_iter)
    with ProcessPoolExecutor() as ppe:
        ppe_iter = ppe.map(f_process1, range(10))
        ppe_result = list(ppe_iter)
    assert hasattr(ray_iter, "__iter__")
    assert hasattr(ray_iter, "__next__")
    assert hasattr(ppe_iter, "__iter__")
    assert hasattr(ppe_iter, "__next__")
    assert type(ray_result) == type(ppe_result)
    assert sorted(ray_result) == sorted(ppe_result)


def test_conformity_with_threadpool():
    def f_process0(x):
        return len([i for i in range(x) if i % 2 == 0])

    assert f_process0.__code__.co_code == f_process1.__code__.co_code

    with RayExecutor() as ex:
        ray_result = ex.submit(f_process0, 100)
    with ThreadPoolExecutor() as tpe:
        tpe_result = tpe.submit(f_process1, 100)
    assert type(ray_result) == type(tpe_result)
    assert ray_result.result() == tpe_result.result()


def test_conformity_with_threadpool_map():
    def f_process0(x):
        return len([i for i in range(x) if i % 2 == 0])

    assert f_process0.__code__.co_code == f_process1.__code__.co_code

    with RayExecutor() as ex:
        ray_iter = ex.map(f_process0, range(10))
        ray_result = list(ray_iter)
    with ThreadPoolExecutor() as tpe:
        tpe_iter = tpe.map(f_process1, range(10))
        tpe_result = list(tpe_iter)
    assert hasattr(ray_iter, "__iter__")
    assert hasattr(ray_iter, "__next__")
    assert hasattr(tpe_iter, "__iter__")
    assert hasattr(tpe_iter, "__next__")
    assert type(ray_result) == type(tpe_result)
    assert sorted(ray_result) == sorted(tpe_result)


def test_conformity_with_processpool_using_max_workers():
    def f_process0(x):
        return len([i for i in range(x) if i % 2 == 0])

    assert f_process0.__code__.co_code == f_process1.__code__.co_code

    with RayExecutor(max_workers=2) as ex:
        ray_result = ex.submit(f_process0, 100).result()
    with ProcessPoolExecutor(max_workers=2) as ppe:
        ppe_result = ppe.submit(f_process1, 100).result()
    assert type(ray_result) == type(ppe_result)
    assert ray_result == ppe_result


def test_conformity_with_processpool_map_using_max_workers():
    def f_process0(x):
        return len([i for i in range(x) if i % 2 == 0])

    assert f_process0.__code__.co_code == f_process1.__code__.co_code

    with RayExecutor(max_workers=2) as ex:
        ray_iter = ex.map(f_process0, range(10))
        ray_result = list(ray_iter)
    with ProcessPoolExecutor(max_workers=2) as ppe:
        ppe_iter = ppe.map(f_process1, range(10))
        ppe_result = list(ppe_iter)
    assert hasattr(ray_iter, "__iter__")
    assert hasattr(ray_iter, "__next__")
    assert hasattr(ppe_iter, "__iter__")
    assert hasattr(ppe_iter, "__next__")
    assert type(ray_result) == type(ppe_result)
    assert sorted(ray_result) == sorted(ppe_result)


def test_conformity_with_threadpool_using_max_workers():
    def f_process0(x):
        return len([i for i in range(x) if i % 2 == 0])

    assert f_process0.__code__.co_code == f_process1.__code__.co_code

    with RayExecutor(max_workers=2) as ex:
        ray_result = ex.submit(f_process0, 100)
    with ThreadPoolExecutor(max_workers=2) as tpe:
        tpe_result = tpe.submit(f_process1, 100)
    assert type(ray_result) == type(tpe_result)
    assert ray_result.result() == tpe_result.result()


def test_conformity_with_threadpool_map_using_max_workers():
    def f_process0(x):
        return len([i for i in range(x) if i % 2 == 0])

    assert f_process0.__code__.co_code == f_process1.__code__.co_code

    with RayExecutor(max_workers=2) as ex:
        ray_iter = ex.map(f_process0, range(10))
        ray_result = list(ray_iter)
    with ThreadPoolExecutor(max_workers=2) as tpe:
        tpe_iter = tpe.map(f_process1, range(10))
        tpe_result = list(tpe_iter)
    assert hasattr(ray_iter, "__iter__")
    assert hasattr(ray_iter, "__next__")
    assert hasattr(tpe_iter, "__iter__")
    assert hasattr(tpe_iter, "__next__")
    assert type(ray_result) == type(tpe_result)
    assert sorted(ray_result) == sorted(tpe_result)


if __name__ == "__main__":
    if os.environ.get("PARALLEL_CI"):
        sys.exit(pytest.main(["-n", "auto", "--boxed", "-vs", __file__]))
    else:
        sys.exit(pytest.main(["-sv", __file__]))
