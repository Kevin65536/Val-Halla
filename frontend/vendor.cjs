const fs = require('node:fs');
const path = require('node:path');
const destination = path.resolve(__dirname, '../src/web/static/vendor');
fs.mkdirSync(destination, {recursive: true});
for (const [source, name] of [
  ['alpinejs/dist/cdn.min.js', 'alpine.min.js'],
  ['tailwindcss/LICENSE', 'tailwind-LICENSE.txt']
]) fs.copyFileSync(path.join(__dirname, 'node_modules', source), path.join(destination, name));

fs.copyFileSync(path.join(__dirname, 'licenses/alpine-LICENSE.md'), path.join(destination, 'alpine-LICENSE.md'));
