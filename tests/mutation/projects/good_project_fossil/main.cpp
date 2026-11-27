#include <memory>
int main(){auto p=std::make_unique<int>(1);return *p;}
