"""Build the deterministic Android fixture using an installed SDK, without Gradle."""
import argparse
import os
from pathlib import Path
import shutil
import subprocess
import zipfile


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sdk", type=Path, required=True)
    p.add_argument("--java-home", type=Path, required=True, help="JDK 17+ used by Android build-tools")
    p.add_argument("--build-tools", default="36.0.0")
    p.add_argument("--platform", default="android-37.0")
    p.add_argument("--out", type=Path, default=Path("build/fixture"))
    a = p.parse_args()
    root = Path(__file__).resolve().parents[1]
    source = root/"fixture-app"
    out = a.out.resolve()
    out.mkdir(parents=True, exist_ok=False)
    for name in ["gen", "classes", "dex"]:
        (out/name).mkdir()
    env = os.environ.copy()
    env["JAVA_HOME"] = str(a.java_home.resolve())
    env["PATH"] = str(a.java_home.resolve()/"bin")+os.pathsep+env["PATH"]
    tools = a.sdk.resolve()/"build-tools"/a.build_tools
    jar = a.sdk.resolve()/"platforms"/a.platform/"android.jar"
    suffix = ".exe" if os.name == "nt" else ""
    def tool(name):
        ext = ".bat" if os.name == "nt" and name in ["d8", "apksigner"] else suffix
        return str(tools/(name+ext))
    def call(*args):
        subprocess.run(list(map(str, args)), env=env, check=True)
    apk = out/"unsigned.apk"
    call(tool("aapt"), "package", "-f", "-m", "-M", source/"AndroidManifest.xml", "-S", source/"res", "-I", jar,
         "-F", apk, "-J", out/"gen")
    sources = list((source/"src").rglob("*.java"))+list((out/"gen").rglob("*.java"))
    call(a.java_home/"bin"/("javac"+suffix), "-source", "8", "-target", "8", "-classpath", jar,
         "-d", out/"classes", *sources)
    call(tool("d8"), "--lib", jar, "--output", out/"dex", *list((out/"classes").rglob("*.class")))
    with zipfile.ZipFile(apk, "a", zipfile.ZIP_DEFLATED) as z:
        z.write(out/"dex/classes.dex", "classes.dex")
    aligned = out/"fixture.apk"
    call(tool("zipalign"), "-f", "4", apk, aligned)
    # Public fixture-only debug key. Never used to sign a production application.
    call(a.java_home/"bin"/("keytool"+suffix), "-genkeypair", "-keystore", out/"debug.keystore", "-alias", "fixture",
         "-storepass", "android", "-keypass", "android", "-keyalg", "RSA", "-validity", "3650", "-dname", "CN=Research Fixture")
    call(tool("apksigner"), "sign", "--ks", out/"debug.keystore", "--ks-pass", "pass:android", "--key-pass", "pass:android", aligned)
    call(tool("apksigner"), "verify", aligned)
    print(aligned)


if __name__ == "__main__":
    main()
