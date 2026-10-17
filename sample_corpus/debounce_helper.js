/**
 * Creates a debounced function that delays invoking func until after
 * wait milliseconds have elapsed since the last time the function was invoked.
 */
export function debounce(func, wait = 250) {
    let timeoutId;
    return function executedFunction(...args) {
        const context = this;
        clearTimeout(timeoutId);
        timeoutId = setTimeout(() => {
            func.apply(context, args);
        }, wait);
    };
}

export function throttle(func, limit = 200) {
    let inThrottle;
    return function (...args) {
        if (!inThrottle) {
            func.apply(this, args);
            inThrottle = true;
            setTimeout(() => inThrottle = false, limit);
        }
    };
}
