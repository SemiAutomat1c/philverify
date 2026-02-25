import { initializeApp } from 'firebase/app'
import { getFirestore, collection, query, orderBy, limit, onSnapshot } from 'firebase/firestore'

const firebaseConfig = {
    apiKey: "AIzaSyBmPeo9UfEkPhtBN9pq7xyzFNI2Bw4yue4",
    authDomain: "philverify.firebaseapp.com",
    projectId: "philverify",
    storageBucket: "philverify.firebasestorage.app",
    messagingSenderId: "148970785140",
    appId: "1:978563490222:web:eea2551e0938ff2efaa83f",
}

const app = initializeApp(firebaseConfig)
export const db = getFirestore(app)

/**
 * Subscribe to the 20 most recent verifications in real-time.
 * @param {Function} callback - called with array of docs on each update
 * @param {Function} [onError] - called with Error when Firestore is unreachable (e.g. ad blocker)
 * @returns unsubscribe function
 */
export function subscribeToHistory(callback, onError) {
    const q = query(
        collection(db, 'verifications'),
        orderBy('timestamp', 'desc'),
        limit(20)
    )
    return onSnapshot(
        q,
        (snap) => {
            callback(snap.docs.map(d => ({ id: d.id, ...d.data() })))
        },
        (error) => {
            // Firestore blocked (ERR_BLOCKED_BY_CLIENT from ad blockers) or
            // permission denied — fail fast and let caller fall back to REST.
            console.warn('[PhilVerify] Firestore unavailable:', error.code || error.message)
            if (onError) onError(error)
        }
    )
}
