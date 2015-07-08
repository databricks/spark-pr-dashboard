require.config({
  baseUrl: "/static/js/",
  paths: {
    "jquery": "//cdnjs.cloudflare.com/ajax/libs/jquery/2.1.4/jquery.min",
    "underscore": "//cdnjs.cloudflare.com/ajax/libs/underscore.js/1.8.3/underscore-min",
    "bootstrap": "//maxcdn.bootstrapcdn.com/bootstrap/3.3.5/js/bootstrap.min",
    "marked": "//cdnjs.cloudflare.com/ajax/libs/marked/0.3.2/marked.min",
    "jquery-timeago": "//cdnjs.cloudflare.com/ajax/libs/jquery-timeago/1.4.1/jquery.timeago.min",
    "react": "//cdnjs.cloudflare.com/ajax/libs/react/0.13.3/react",
    "react-mini-router": "libs/react-mini-router"
  },
  shim: {
    "bootstrap": ["jquery"],
    "underscore": {
      exports: "_"
    },
    "backbone": {
      deps: ["underscore", "jquery"],
      exports: "Backbone"
    }
  }
});

require(["app"], function(App) {});
