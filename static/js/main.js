// jscs:disable
require.config({
  baseUrl: "/static/js/",
  paths: {
    "jquery": "//cdnjs.cloudflare.com/ajax/libs/jquery/2.1.1/jquery.min",
    "underscore": "//cdnjs.cloudflare.com/ajax/libs/underscore.js/1.7.0/underscore-min",
    "bootstrap": "//maxcdn.bootstrapcdn.com/bootstrap/3.2.0/js/bootstrap.min",
    "marked": "//cdnjs.cloudflare.com/ajax/libs/marked/0.3.2/marked.min",
    "jquery-timeago": "//cdnjs.cloudflare.com/ajax/libs/jquery-timeago/1.4.0/jquery.timeago.min",
    "gae-mini-profiler": "gae_mini_profiler/static/js/profiler",
    "react": "//cdnjs.cloudflare.com/ajax/libs/react/0.12.0/react",
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
// jscs:enable
