/* module_c.h — third public header (no binding layer present) */
#ifndef MODULE_C_H
#define MODULE_C_H

class ModuleC {
public:
    void configure();
    int status();
    void reset();
    long identify();
};

#endif