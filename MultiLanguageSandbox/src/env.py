import pwd
import grp


USER = "sandbox"
SANDBOX_UID = pwd.getpwnam(USER).pw_uid
SANDBOX_GID = grp.getgrnam(USER).gr_gid
ENV = {
    "USER": USER,
    "HOME": "/home/sandbox",
    "PATH": "/opt/nvm/versions/node/v18.20.8/bin:/home/sandbox/.cargo/bin:/root/.sdkman/candidates/scala/current/bin:/root/.sdkman/candidates/kotlin/current/bin:/opt/conda/envs/py311/bin:/opt/conda/bin:/usr/local/lib/nodejs/node/bin:/usr/local/go/bin:/root/.local/share/coursier/bin:/root/.sdkman/candidates/kotlin/current/bin:/opt/swift-5.9.2-RELEASE-ubuntu22.04/usr/bin:/opt/dart/dart-sdk/bin:/root/.sdkman/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin",
    "SHELL": "/bin/bash",
    "CONDA_DIR": "/opt/conda",
    "SDKMAN_DIR": "/root/.sdkman",
    "PYTHONUNBUFFERED": "1",
    "CARGO_HOME": "/home/sandbox/.cargo",
    "RUSTUP_HOME": "/home/sandbox/.rustup",
    "LC_CTYPE": "C.UTF-8",
    "GOPATH": "/home/sandbox/go",
    "CLASSPATH": "/opt/java_libs/json.jar:/opt/java_libs/junit-platform-console-standalone.jar:/opt/java_libs/gson.jar:."
}