import { ComponentFixture, TestBed } from '@angular/core/testing';

import { ListCyclesComponent } from './list-cycles.component';

describe('ListCyclesComponent', () => {
  let component: ListCyclesComponent;
  let fixture: ComponentFixture<ListCyclesComponent>;

  beforeEach(async () => {
    await TestBed.configureTestingModule({
      declarations: [ ListCyclesComponent ]
    })
    .compileComponents();

    fixture = TestBed.createComponent(ListCyclesComponent);
    component = fixture.componentInstance;
    fixture.detectChanges();
  });

  it('should create', () => {
    expect(component).toBeTruthy();
  });
});
