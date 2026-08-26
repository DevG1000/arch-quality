/* native.c — C library with opaque handles (generic binding target) */
#include <stdlib.h>

void* create_handle(void) {
    return malloc(64);
}

int use_handle(void* handle) {
    return handle ? 1 : 0;
}