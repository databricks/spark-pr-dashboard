module.exports = function(grunt) {
  "use strict";

  grunt.initConfig({
    pkg: grunt.file.readJSON('package.json'),
    react: {
      jsx: {
        files: [
          {
            expand: true,
            cwd: 'static/jsx',
            src: [ '**/*.jsx' ],
            dest: 'static/js',
            ext: '.js'
          }
        ]
      }
    },

    jshint: {
      src: ["Gruntfile.js", "static/js/*.js", "static/jsx/**/*.jsx"],
      options: {
        jshintrc: true
      }
    },

    jscs: {
      src: ["Gruntfile.js", "static/js/*.js", "static/jsx/**/*.jsx"],
      options: {
        config: ".jscs.json"
      }
    },

    watch: {
      react: {
				files: ["Gruntfile.js", "static/**/*.js", "static/**/*.jsx"],
        tasks: ['default']
      }
    }
  });

  // Code quality tool for jsx and js (safe to replace JSHint)
  grunt.loadNpmTasks("grunt-jsxhint");
  // Use the JSX code style checker, since it is aware of both .js and jsx files
  grunt.loadNpmTasks("grunt-jsxcs");

  grunt.loadNpmTasks('grunt-contrib-watch');
  grunt.loadNpmTasks('grunt-react');

  grunt.registerTask("default", ["react", "lint"]);
  grunt.registerTask("lint", ["jscs", "jshint"]);
};
