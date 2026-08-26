/* Tests for the util functions. */

#include <assert.h>

int lookup(int key);
int save_record(int value);


void test_lookup(void) {
    assert(lookup(2) == 4);
}


void test_save_record(void) {
    assert(save_record(3) == 4);
}