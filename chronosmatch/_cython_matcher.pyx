# cython: language_level=3, boundscheck=False, wraparound=False

from cpython.mem cimport PyMem_Free, PyMem_Malloc
from libc.stdint cimport int64_t


cpdef tuple match_orders(
    double incoming_price,
    long long incoming_quantity,
    bint incoming_is_buy,
    double[:] resting_prices,
    long long[:] resting_quantities,
):
    cdef Py_ssize_t count = resting_prices.shape[0]
    if count == 0:
        return [], incoming_quantity
    cdef Py_ssize_t index
    cdef int64_t remaining = incoming_quantity
    cdef int64_t fill
    cdef int64_t* fills = <int64_t*>PyMem_Malloc(count * sizeof(int64_t))
    if count and fills == NULL:
        raise MemoryError()

    try:
        for index in range(count):
            fills[index] = 0

        with nogil:
            for index in range(count):
                if remaining <= 0:
                    break
                if incoming_is_buy:
                    if resting_prices[index] > incoming_price:
                        break
                else:
                    if resting_prices[index] < incoming_price:
                        break
                fill = remaining
                if resting_quantities[index] < fill:
                    fill = resting_quantities[index]
                fills[index] = fill
                remaining -= fill

        return [fills[index] for index in range(count)], remaining
    finally:
        PyMem_Free(fills)
