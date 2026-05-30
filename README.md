# monkey-business — App Engine redirect shim

This branch (`appengine`) is the App Engine deployment of `monkey-business.appspot.com`. It exists only to 301-redirect every incoming request to the live site at https://apwest.github.io/monkey-business/.

The actual site lives on the `master` branch and is served by GitHub Pages.

## Deploying

From this branch:

```
gcloud app deploy
```
