// # Settings - Change this one line when switching local <-> GitHub Pages
const WindowBaseUrl = window.location.origin + "/map/";    // GitHub Pages
// const WindowBaseUrl = window.location.origin;              // Live server

const initPhotos = 1; // Determine range of photos to be shown on slideshows and in posts


// Utility function to run a function if the object is defined
function runIfDefined(obj, fn) {
    if (obj && typeof fn === 'function') {
        fn();
    }
}

document.addEventListener('DOMContentLoaded', () => {
    // Random Photo
    runIfDefined(window.MyRandomPhoto, () => {
        MyRandomPhoto.init({
            WindowBaseUrl: WindowBaseUrl,
            initPhotos: initPhotos,
        });
    });

    // Post Container
    runIfDefined(window.MyPostContainerModule, () => {
        MyPostContainerModule.init({
            WindowBaseUrl: WindowBaseUrl,
        });
    });

    // Slideshow
    runIfDefined(window.MySlideshowModule, () => {
        MySlideshowModule.init({
            initSpeed: 3,
            maxSpeed: 10,
            minSpeed: 1.75,
            stepSpeed: 0.25,
            initQuality: 4,
            SLIDESHOW_HIDDEN: true,
            SLIDESHOW_VISIBLE: false,
            randomizeImages: true,
            defaultImgSrc_png: "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEicpyIovkBboaA3DOVcPNZQQ47-GSa5AidzIeUbL2N8iue6yM1XIxd0BL5W8e2ty7ntqz4K8ovfmT7DV1c3_NXVFWWDLeKYMpbD_C1wK1qh4Y1zGLh_tHUi5d1pHtDxxQKunZLAkL3ibt5gjhI3KQX9cHtQMn0m9liFgtLc00VQH4YHc5I6aAO-mw84w8Q/s600/end_cover_photo.png",
            defaultImgSrc: "https://blogger.googleusercontent.com/img/b/R29vZ2xl/AVvXsEiU8RYSJ0I45O63GlKYXw5-U_r7GwP48_st9F1LG7_Z3STuILVQxMO4qLgzP_wxg0v_77s-YwidwwZQIDS1K6SUmY-W3QMwcIyEvt28cLalvCVQu4qWTQIm-B_FvgEmCCe6ydGld4fQgMMd2xNdqMMFtuHgeVXB4gRPco3XP90OOKHpf6HyZ6AeEZqNJQo/s1600/IMG20241101141924.jpg",
            doubleClickThreshold: 300,
            WindowBaseUrl: WindowBaseUrl,
        });
    });

    // Slideshow filters
    runIfDefined(window.FilterSlideshowModule, () => {
        FilterSlideshowModule.init({
            initPhotos: initPhotos,
            isRelive: true
        });
    });

    // Gallery
    runIfDefined(window.GalleryModule, () => {
        GalleryModule.init({
            WindowBaseUrl: WindowBaseUrl,
            randomizeImages: true,
            initPhotos: initPhotos,
        });
    });

    // Peak List
    runIfDefined(window.PeakListModule, () => {
        PeakListModule.init({
            WindowBaseUrl: WindowBaseUrl,
        }); 
    });
});