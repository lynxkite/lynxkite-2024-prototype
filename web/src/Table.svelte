<script lang="ts">
  import {TabulatorFull as Tabulator} from 'tabulator-tables';
  import {onMount} from 'svelte';

  export let data, columns;

  let tableComponent;
  let tab;

  // The rows in the data are arrays, but Tabulator expects objects.
  const objs = [];
  $: {
    objs.splice();
    for (const row of data) {
      const obj = {};
      for (let i = 0; i < columns.length; i++) {
        let d = row[i];
        if (typeof d !== 'string' && typeof d !== 'number') {
          d = JSON.stringify(d);
        }
        obj[columns[i]] = d;
      }
      objs.push(obj);
    }
  }

  onMount(() => {
    tab = new Tabulator(tableComponent, {
      data: objs,
      columns: columns.map(c => ({title: c, field: c, widthGrow: 1})),
      height: '311px',
      reactiveData: true,
      layout: "fitColumns",
    });
  });
</script>

<div bind:this={tableComponent}></div>
