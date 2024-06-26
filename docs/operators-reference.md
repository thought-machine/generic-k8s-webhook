When defining a condition, we can use any of the following operators.

- [const](#const)
- [getValue](#getvalue)
- [and](#and)
- [or](#or)
- [not](#not)
- [equal](#equal)
- [sum](#sum)
- [forEach](#foreach)

#### const

Defines a constant value. It is normally used with the [equal](#equal) operator, in case we want to check that a field in the manifest equals to a value that we define (using the `const` operator).

```yaml
const: <constant value>
```

#### getValue

Retrieves a value defined in the manifest. The `<path>` is a `.` (dot) separated path that references a field in the manifest. For example, `.metadata.name`. If the `getValue` is used nested within the [forEach](#foreach) operator, by default it will take as a base context the item that the [forEach](#foreach) is iterating. If you want to use the root of the manifest as the context, then you must add a `$` at the beginning of the path. For example, `$.metadata.name` will always resolve to the metadata defined at the root level independently if the `getValue` is nested in a [forEach](#foreach) or not.

```yaml
# Refers to the latest context
getValue: .metadata.name

# Refers always to the root context
getValue: $.metadata.name
```

#### and

It performs an `and` operation on a list of elements. The list of elements can be explicitly defined (an actual yaml list) or implicitly defined. This last case is exemplified when the `and` consumes the result generated by the [forEach](#foreach) operator.

```yaml
and:
  - <elem1>
  - <elem2>
  - ...

and:
  forEach:
    ...
```

#### or

It performs an `or` operation on a list of elements. The list of elements can be explicitly defined (an actual yaml list) or implicitly defined. This last case is exemplified when the `or` consumes the result generated by the [forEach](#foreach) operator.

```yaml
or:
  - <elem1>
  - <elem2>
  - ...

or:
  forEach:
    ...
```

#### not

It negates the value of its argument.

```yaml
not:
  <operator>

not:
  and:
    - ...
```

#### equal

Compares two elements and returns true if they are equal.

```yaml
equal:
  - const: default
  - getValue: .metadata.namespace
```

#### sum

Sums the values of a list of elements. The list of elements can be explicitly defined (an actual yaml list) or implicitly defined. This last case is exemplified when the `sum` consumes the result generated by the [forEach](#foreach) operator.

```yaml
sum:
  - const: 1
  - const: 4

sum:
  forEach:
    ...
```

#### forEach

It's like a `map` operation. If executes the operation `op` for each element defined in `elements`. It returns the transformed list of elements. The [getValue](#getvalue) operator that lives within a `forEach` receives as context the current element that the `forEach` is iterating. In this example, `.name` resolves to the name of a container.

```yaml
forEach:
  elements: {getValue: .spec.containers}
  op:
    equal:
      - const: my-side-car
      - getValue: .name
```
