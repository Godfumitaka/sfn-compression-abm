# 段3の小例（元の伏せ辺がglueだった日）

種1・試行添字5・世界1。関係のID・引数・述語を印字する。

## skeleton

完全場面：3実体、19関係。公開場面：3実体。

original_held_out:
```json
{
  "id": "e3ebe4a797dede42",
  "predicate": "beside",
  "arguments": [
    "5da0462fd7b02364",
    "98ab371fa6e82941"
  ]
}
```

held_out:
```json
{
  "id": "6877a6ec33a2d094",
  "predicate": "break",
  "arguments": [
    "946f56b6120053d9",
    "5da0462fd7b02364"
  ]
}
```

removed:
```json
[
  {
    "id": "e3ebe4a797dede42",
    "predicate": "beside",
    "arguments": [
      "5da0462fd7b02364",
      "98ab371fa6e82941"
    ]
  },
  {
    "id": "99cf1a7b5da39320",
    "predicate": "inside",
    "arguments": [
      "5da0462fd7b02364",
      "98ab371fa6e82941"
    ]
  },
  {
    "id": "c94b938f4cf2a315",
    "predicate": "inside",
    "arguments": [
      "5da0462fd7b02364",
      "98ab371fa6e82941"
    ]
  }
]
```

added:
```json
[]
```

ドア・シール・link:
```json
[
  {
    "id": "e14b89702df3e83c",
    "predicate": "hold",
    "arguments": [
      "946f56b6120053d9",
      "5da0462fd7b02364"
    ]
  },
  {
    "id": "678d19e3d13afc1c",
    "predicate": "sig_n",
    "arguments": [
      "946f56b6120053d9"
    ]
  },
  {
    "id": "4cf2633d6dd3a950",
    "predicate": "attach",
    "arguments": [
      "678d19e3d13afc1c",
      "01e1c9219a0b7bcb"
    ]
  }
]
```

## current

完全場面：3実体、22関係。公開場面：3実体。

original_held_out:
```json
{
  "id": "e3ebe4a797dede42",
  "predicate": "beside",
  "arguments": [
    "5da0462fd7b02364",
    "98ab371fa6e82941"
  ]
}
```

held_out:
```json
{
  "id": "e3ebe4a797dede42",
  "predicate": "beside",
  "arguments": [
    "5da0462fd7b02364",
    "98ab371fa6e82941"
  ]
}
```

removed:
```json
[]
```

added:
```json
[]
```

ドア・シール・link:
```json
[
  {
    "id": "e14b89702df3e83c",
    "predicate": "hold",
    "arguments": [
      "946f56b6120053d9",
      "5da0462fd7b02364"
    ]
  },
  {
    "id": "678d19e3d13afc1c",
    "predicate": "sig_n",
    "arguments": [
      "946f56b6120053d9"
    ]
  },
  {
    "id": "4cf2633d6dd3a950",
    "predicate": "attach",
    "arguments": [
      "678d19e3d13afc1c",
      "01e1c9219a0b7bcb"
    ]
  }
]
```

## plus4

完全場面：3実体、26関係。公開場面：3実体。

original_held_out:
```json
{
  "id": "e3ebe4a797dede42",
  "predicate": "beside",
  "arguments": [
    "5da0462fd7b02364",
    "98ab371fa6e82941"
  ]
}
```

held_out:
```json
{
  "id": "e3ebe4a797dede42",
  "predicate": "beside",
  "arguments": [
    "5da0462fd7b02364",
    "98ab371fa6e82941"
  ]
}
```

removed:
```json
[]
```

added:
```json
[
  {
    "id": "9bb5fcc91b8b9b08",
    "predicate": "dz_12",
    "arguments": [
      "5da0462fd7b02364"
    ]
  },
  {
    "id": "7bf4ddc47bad0582",
    "predicate": "dz_9",
    "arguments": [
      "5da0462fd7b02364"
    ]
  },
  {
    "id": "01a5be6c2250713e",
    "predicate": "dz_8",
    "arguments": [
      "946f56b6120053d9"
    ]
  },
  {
    "id": "04e68866c08bc6e1",
    "predicate": "dz_6",
    "arguments": [
      "5da0462fd7b02364"
    ]
  }
]
```

ドア・シール・link:
```json
[
  {
    "id": "e14b89702df3e83c",
    "predicate": "hold",
    "arguments": [
      "946f56b6120053d9",
      "5da0462fd7b02364"
    ]
  },
  {
    "id": "678d19e3d13afc1c",
    "predicate": "sig_n",
    "arguments": [
      "946f56b6120053d9"
    ]
  },
  {
    "id": "4cf2633d6dd3a950",
    "predicate": "attach",
    "arguments": [
      "678d19e3d13afc1c",
      "01e1c9219a0b7bcb"
    ]
  }
]
```

## plus8

完全場面：3実体、30関係。公開場面：3実体。

original_held_out:
```json
{
  "id": "e3ebe4a797dede42",
  "predicate": "beside",
  "arguments": [
    "5da0462fd7b02364",
    "98ab371fa6e82941"
  ]
}
```

held_out:
```json
{
  "id": "e3ebe4a797dede42",
  "predicate": "beside",
  "arguments": [
    "5da0462fd7b02364",
    "98ab371fa6e82941"
  ]
}
```

removed:
```json
[]
```

added:
```json
[
  {
    "id": "9bb5fcc91b8b9b08",
    "predicate": "dz_12",
    "arguments": [
      "5da0462fd7b02364"
    ]
  },
  {
    "id": "7bf4ddc47bad0582",
    "predicate": "dz_9",
    "arguments": [
      "5da0462fd7b02364"
    ]
  },
  {
    "id": "01a5be6c2250713e",
    "predicate": "dz_8",
    "arguments": [
      "946f56b6120053d9"
    ]
  },
  {
    "id": "04e68866c08bc6e1",
    "predicate": "dz_6",
    "arguments": [
      "5da0462fd7b02364"
    ]
  },
  {
    "id": "8626219d3214d27b",
    "predicate": "dz_1",
    "arguments": [
      "946f56b6120053d9"
    ]
  },
  {
    "id": "80597914169e7fb8",
    "predicate": "dz_11",
    "arguments": [
      "5da0462fd7b02364"
    ]
  },
  {
    "id": "ab2f863c4846b6d8",
    "predicate": "dz_2",
    "arguments": [
      "946f56b6120053d9"
    ]
  },
  {
    "id": "1fc4ae9ab5c36877",
    "predicate": "dz_7",
    "arguments": [
      "946f56b6120053d9"
    ]
  }
]
```

ドア・シール・link:
```json
[
  {
    "id": "e14b89702df3e83c",
    "predicate": "hold",
    "arguments": [
      "946f56b6120053d9",
      "5da0462fd7b02364"
    ]
  },
  {
    "id": "678d19e3d13afc1c",
    "predicate": "sig_n",
    "arguments": [
      "946f56b6120053d9"
    ]
  },
  {
    "id": "4cf2633d6dd3a950",
    "predicate": "attach",
    "arguments": [
      "678d19e3d13afc1c",
      "01e1c9219a0b7bcb"
    ]
  }
]
```

