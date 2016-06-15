define([
    'underscore'
  ],
  function(_) {
    "use strict";

    var UrlMixin = {
      getAnchor: function(component) {
        //remove whitespaces and convert to lower case
        return component.replace(/ /g,'').toLowerCase();
      },

      pushAnchor: function(component, staleOpt) {
        var anchor = this.getAnchor(component);
        if (typeof staleOpt !== 'undefined') {
          anchor = this.getAnchor(staleOpt) + '&' + anchor;
        }
        window.location.hash = anchor;
      }
    };

    return UrlMixin;
  }
);
