// jscs:disable
define([
    'underscore'
  ],
  function(_) {
    "use strict";

    // jscs:enable
    var UrlMixin = {
      getAnchor: function(component) {
        //remove whitespaces and convert to lower case
        return component.replace(/ /g,'').toLowerCase();
      },

      pushAnchor: function(component) {
        var anchor = this.getAnchor(component);
        window.location.hash = anchor;
      }
    };

    return UrlMixin;
  }
);
