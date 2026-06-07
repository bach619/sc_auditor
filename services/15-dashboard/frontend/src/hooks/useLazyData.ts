import { useEffect, useRef, useState } from 'react';

export function useLazyData<T>(fetchFn: () => Promise<T>) {
    const [data, setData] = useState<T | null>(null);
    const [loading, setLoading] = useState(false);
    const ref = useRef<HTMLDivElement>(null);
    
    useEffect(() => {
        const observer = new IntersectionObserver(
            ([entry]) => {
                if (entry.isIntersecting && !data && !loading) {
                    setLoading(true);
                    fetchFn().then(setData).finally(() => setLoading(false));
                }
            },
            { rootMargin: '200px' }
        );
        
        const el = ref.current;
        if (el) observer.observe(el);
        return () => { if (el) observer.unobserve(el); };
    }, [fetchFn, data, loading]);
    
    return { ref, data, loading };
}
