# Firebase Security Checklist

## 1. Restrict the API Key (Google Cloud Console)
1. Go to https://console.cloud.google.com/apis/credentials
2. Select the API key used by this project.
3. Under **Application restrictions**:
   - Choose **HTTP referrers**
   - Add your domains (e.g. `https://your-site.netlify.app/*`, `http://localhost:*`)
4. Under **API restrictions**:
   - Restrict to only Firebase / the APIs you actually use.

## 2. Firestore Security Rules (paste in Firebase Console → Firestore → Rules)

```js
rules_version = '2';
service cloud.firestore {
  match /databases/{database}/documents {
    // Only the authorized email can read/write
    match /{document=**} {
      allow read, write: if request.auth != null
                         && request.auth.token.email == "billianiramiro00@gmail.com";
    }
  }
}
```

## 3. Restore the config
The `index.html` currently has a placeholder. Replace `YOUR_FIREBASE_API_KEY_HERE` with your real key **after** applying the restrictions above.

Never commit unrestricted keys again.
