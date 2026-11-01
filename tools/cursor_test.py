import io
p = r"E:\RAYS\Desktop\workspace\mousecam\rust\mc-engine\src\camera.rs"
s = io.open(p, encoding="utf-8").read()
if "mod cursor_scale" not in s:
    s += '''
#[cfg(test)]
mod cursor_scale {
    use super::growth_factor;

    #[test]
    fn resting_viewport_does_not_scale_the_cursor() {
        // src_w equals out_w/zoom, i.e. no speed expansion
        assert!((growth_factor(1080.0, 1080, 1.0) - 1.0).abs() < 1e-6);
        assert!((growth_factor(540.0, 1080, 2.0) - 1.0).abs() < 1e-6);
    }

    #[test]
    fn expansion_scales_the_cursor_by_the_same_factor() {
        // 1.2x and 1.5x expansion at zoom 1
        assert!((growth_factor(1296.0, 1080, 1.0) - 1.2).abs() < 1e-4);
        assert!((growth_factor(1620.0, 1080, 1.0) - 1.5).abs() < 1e-4);
    }

    #[test]
    fn growth_is_clamped_and_never_shrinks() {
        assert_eq!(growth_factor(900.0, 1080, 1.0), 1.0); // smaller than rest -> 1.0
        assert_eq!(growth_factor(99_999.0, 1080, 1.0), 4.0); // absurd -> 4.0
    }
}
'''
    io.open(p, "w", encoding="utf-8", newline="").write(s)
    print("tests added")
