# Unified plugin registration mechanism
class Plugin {
public:
    virtual ~Plugin() {}
    virtual const char* name() const = 0;
};

// @deprecated use registerV2
void registerPlugin(Plugin* p) {
    // plugin registry
}

// version = "2.0.0"
