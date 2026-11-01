fn main() {
    let cwd = std::env::current_dir().map(|p| p.display().to_string()).unwrap_or_default();
    println!("cwd = {cwd}");
    for p in [
        r"C:\Users\ray\mc-test\rec_probe",
        r"E:\RAYS\Videos\MouseCam\rec_probe2",
        r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\captures\rec_probe3",
    ] {
        match std::fs::create_dir_all(p) {
            Ok(_) => println!("OK   {p}"),
            Err(e) => println!("FAIL {p}: {e}"),
        }
    }
}
