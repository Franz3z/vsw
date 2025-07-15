import resolve from '@rollup/plugin-node-resolve';
import commonjs from '@rollup/plugin-commonjs';

export default {
  input: 'src/whiteboard.js',           
  output: {
    file: 'static/bundle.js',           
    format: 'es',                       
    sourcemap: true                     
  },
  plugins: [
    resolve(),                          
    commonjs()                          
  ]
};
