#include <unistd.h>
#include <stdlib.h>
#include <libgen.h>
#include <mach-o/dyld.h>
#include <stdio.h>

int main() {
    char path[1024];
    uint32_t size = sizeof(path);
    if (_NSGetExecutablePath(path, &size) == 0) {
        char *dir = dirname(path);
        char script_path[2048];
        snprintf(script_path, sizeof(script_path), "%s/agent_engine.sh", dir);
        
        char *args[] = {"/bin/bash", script_path, NULL};
        execv(args[0], args);
    }
    return 1;
}
