#include <memory>
void f(){std::auto_ptr<int> p(new int(1));}
static void legacy_init(){}
